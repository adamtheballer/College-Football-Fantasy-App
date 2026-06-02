from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.scheduled_league_job import ScheduledLeagueJob
from collegefootballfantasy_api.app.services.event_stream import append_league_event
from collegefootballfantasy_api.app.services.waiver_engine import process_pending_waiver_claims
from collegefootballfantasy_api.app.services.week_scoring_runner import execute_week_scoring_run

QUEUED = "queued"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
SUPPORTED_JOB_TYPES = {"waiver_process", "week_scores_recompute"}


@dataclass
class JobRunResult:
    job_id: int
    job_type: str
    status: str
    detail: str | None = None


@dataclass
class RunDueJobsResult:
    worker_id: str
    processed: int
    completed: int
    failed: int
    results: list[JobRunResult]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_job(
    db: Session,
    *,
    league_id: int,
    job_type: str,
    run_at: datetime,
    payload: dict | None,
    created_by_user_id: int | None,
    max_attempts: int = 3,
) -> ScheduledLeagueJob:
    normalized = (job_type or "").strip().lower()
    if normalized not in SUPPORTED_JOB_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported job_type: {job_type}")

    job = ScheduledLeagueJob(
        league_id=league_id,
        job_type=normalized,
        status=QUEUED,
        run_at=run_at,
        payload=payload or {},
        attempts=0,
        max_attempts=max(1, int(max_attempts or 3)),
        created_by_user_id=created_by_user_id,
    )
    db.add(job)
    db.flush()

    append_league_event(
        db,
        league_id=league_id,
        event_type="league.job.queued",
        entity_type="scheduled_job",
        entity_id=job.id,
        payload={
            "job_id": job.id,
            "job_type": job.job_type,
            "run_at": job.run_at.isoformat(),
        },
    )
    return job


def _claim_due_jobs(
    db: Session,
    *,
    league_id: int,
    worker_id: str,
    limit: int,
) -> list[ScheduledLeagueJob]:
    due_rows = (
        db.query(ScheduledLeagueJob)
        .filter(
            ScheduledLeagueJob.league_id == league_id,
            ScheduledLeagueJob.status == QUEUED,
            ScheduledLeagueJob.run_at <= now_utc(),
        )
        .order_by(ScheduledLeagueJob.run_at.asc(), ScheduledLeagueJob.id.asc())
        .limit(max(1, min(limit, 100)))
        .all()
    )

    claimed: list[ScheduledLeagueJob] = []
    for row in due_rows:
        if row.status != QUEUED:
            continue
        row.status = RUNNING
        row.locked_by = worker_id
        row.locked_at = now_utc()
        row.last_error = None
        row.attempts = int(row.attempts or 0) + 1
        db.add(row)
        claimed.append(row)

    db.flush()
    return claimed


def _run_single_job(db: Session, *, job: ScheduledLeagueJob, worker_id: str) -> JobRunResult:
    try:
        if job.job_type == "waiver_process":
            batch_key = str((job.payload or {}).get("batch_key") or f"job-{job.id}-{int(now_utc().timestamp())}")
            execution = process_pending_waiver_claims(
                db,
                league_id=job.league_id,
                acted_by_user_id=job.created_by_user_id,
                batch_key=batch_key,
            )
            detail = (
                f"processed={execution.response.processed_count}, won={execution.response.won_count}, "
                f"lost={execution.response.lost_count}, invalid={execution.response.invalid_count}"
            )
        elif job.job_type == "week_scores_recompute":
            payload = job.payload or {}
            season = int(payload.get("season"))
            week = int(payload.get("week"))
            source_mode = str(payload.get("source_mode") or "actual_then_projection")
            finalize_matchups = bool(payload.get("finalize_matchups", False))
            finalize_week = bool(payload.get("finalize_week", False))
            note = payload.get("note")
            execution = execute_week_scoring_run(
                db,
                league_id=job.league_id,
                season=season,
                week=week,
                source_mode=source_mode,
                finalize_matchups=finalize_matchups,
                finalize_week=finalize_week,
                note=note if isinstance(note, str) else None,
                created_by_user_id=job.created_by_user_id,
            )
            detail = (
                f"teams={len(execution.scoring_result.team_scores)}, matchups={len(execution.scoring_result.matchup_scores)}, "
                f"state={execution.week_state.status}, standings={execution.standings_count}"
            )
        else:
            raise RuntimeError(f"unsupported scheduled job type: {job.job_type}")

        job.status = COMPLETED
        job.completed_at = now_utc()
        db.add(job)
        append_league_event(
            db,
            league_id=job.league_id,
            event_type="league.job.completed",
            entity_type="scheduled_job",
            entity_id=job.id,
            payload={
                "job_id": job.id,
                "job_type": job.job_type,
                "worker_id": worker_id,
                "detail": detail,
            },
        )
        return JobRunResult(job_id=job.id, job_type=job.job_type, status=COMPLETED, detail=detail)
    except Exception as exc:
        terminal = int(job.attempts or 0) >= int(job.max_attempts or 1)
        job.status = FAILED if terminal else QUEUED
        job.failed_at = now_utc()
        job.last_error = str(exc)[:500]
        job.locked_by = None
        job.locked_at = None
        if not terminal:
            # retry soon
            job.run_at = now_utc()
        db.add(job)
        append_league_event(
            db,
            league_id=job.league_id,
            event_type="league.job.failed",
            entity_type="scheduled_job",
            entity_id=job.id,
            payload={
                "job_id": job.id,
                "job_type": job.job_type,
                "worker_id": worker_id,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
                "terminal": terminal,
                "error": str(exc)[:500],
            },
        )
        return JobRunResult(job_id=job.id, job_type=job.job_type, status=job.status, detail=str(exc)[:500])


def run_due_jobs_for_league(
    db: Session,
    *,
    league_id: int,
    worker_id: str,
    limit: int = 20,
) -> RunDueJobsResult:
    claimed = _claim_due_jobs(db, league_id=league_id, worker_id=worker_id, limit=limit)
    results: list[JobRunResult] = []
    for row in claimed:
        results.append(_run_single_job(db, job=row, worker_id=worker_id))

    completed = sum(1 for row in results if row.status == COMPLETED)
    failed = sum(1 for row in results if row.status == FAILED)
    db.flush()
    return RunDueJobsResult(
        worker_id=worker_id,
        processed=len(results),
        completed=completed,
        failed=failed,
        results=results,
    )
