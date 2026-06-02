from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, get_league_or_404, require_commissioner, require_league_member
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.scheduled_league_job import ScheduledLeagueJob
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.automation import (
    LeagueAutomationJobList,
    LeagueAutomationJobRead,
    LeagueAutomationJobScheduleRequest,
    LeagueAutomationRunDueRequest,
    LeagueAutomationRunDueResponse,
    LeagueAutomationRunDueResultRow,
)
from collegefootballfantasy_api.app.services.admin_actions import append_admin_action
from collegefootballfantasy_api.app.services.idempotency import (
    begin_idempotent_request,
    complete_idempotent_request,
    fail_idempotent_request,
)
from collegefootballfantasy_api.app.services.job_queue import enqueue_job, run_due_jobs_for_league

router = APIRouter()


def _to_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize(row: ScheduledLeagueJob) -> LeagueAutomationJobRead:
    return LeagueAutomationJobRead(
        id=row.id,
        league_id=row.league_id,
        job_type=row.job_type,
        status=row.status,
        run_at=row.run_at,
        payload=row.payload or {},
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        locked_by=row.locked_by,
        locked_at=row.locked_at,
        completed_at=row.completed_at,
        failed_at=row.failed_at,
        last_error=row.last_error,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post(
    "/leagues/{league_id}/automation/jobs",
    response_model=LeagueAutomationJobRead,
    status_code=status.HTTP_201_CREATED,
)
def schedule_league_job_endpoint(
    league_id: int,
    payload: LeagueAutomationJobScheduleRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueAutomationJobRead:
    league, _membership = require_commissioner(db, league_id, current_user)
    idem = begin_idempotent_request(
        db,
        scope=f"league:{league.id}:automation:schedule",
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)

    run_at = _to_utc(payload.run_at)
    try:
        job = enqueue_job(
            db,
            league_id=league.id,
            job_type=payload.job_type,
            run_at=run_at,
            payload=payload.payload,
            created_by_user_id=current_user.id,
            max_attempts=payload.max_attempts,
        )
        append_admin_action(
            db,
            league_id=league.id,
            actor_user_id=current_user.id,
            action_type="automation.job.scheduled",
            target_type="scheduled_job",
            target_id=job.id,
            metadata={
                "job_type": job.job_type,
                "run_at": job.run_at.isoformat(),
                "max_attempts": job.max_attempts,
            },
        )
        db.flush()
        response_payload = _serialize(job).model_dump(mode="json")
        complete_idempotent_request(
            db,
            start=idem,
            response_status_code=status.HTTP_201_CREATED,
            response_payload=response_payload,
        )
        db.commit()
        return response_payload
    except Exception:
        fail_idempotent_request(db, start=idem)
        db.commit()
        raise


@router.get("/leagues/{league_id}/automation/jobs", response_model=LeagueAutomationJobList)
def list_league_jobs_endpoint(
    league_id: int,
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueAutomationJobList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)

    query = db.query(ScheduledLeagueJob).filter(ScheduledLeagueJob.league_id == league.id)
    if status_filter:
        query = query.filter(ScheduledLeagueJob.status == status_filter.strip().lower())

    total = query.count()
    rows = (
        query.order_by(ScheduledLeagueJob.run_at.desc(), ScheduledLeagueJob.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return LeagueAutomationJobList(
        data=[_serialize(row) for row in rows],
        total=total,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )


@router.post("/leagues/{league_id}/automation/jobs/run-due", response_model=LeagueAutomationRunDueResponse)
def run_due_league_jobs_endpoint(
    league_id: int,
    payload: LeagueAutomationRunDueRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueAutomationRunDueResponse:
    league, _membership = require_commissioner(db, league_id, current_user)
    idem = begin_idempotent_request(
        db,
        scope=f"league:{league.id}:automation:run_due",
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)

    try:
        result = run_due_jobs_for_league(
            db,
            league_id=league.id,
            worker_id=f"api:{current_user.id}",
            limit=payload.limit,
        )
        append_admin_action(
            db,
            league_id=league.id,
            actor_user_id=current_user.id,
            action_type="automation.jobs.run_due",
            target_type="league",
            target_id=league.id,
            metadata={
                "worker_id": result.worker_id,
                "limit": payload.limit,
                "processed": result.processed,
                "completed": result.completed,
                "failed": result.failed,
            },
        )
        response_payload = LeagueAutomationRunDueResponse(
            worker_id=result.worker_id,
            processed=result.processed,
            completed=result.completed,
            failed=result.failed,
            results=[
                LeagueAutomationRunDueResultRow(
                    job_id=row.job_id,
                    job_type=row.job_type,
                    status=row.status,
                    detail=row.detail,
                )
                for row in result.results
            ],
        ).model_dump(mode="json")
        complete_idempotent_request(
            db,
            start=idem,
            response_status_code=status.HTTP_200_OK,
            response_payload=response_payload,
        )
        db.commit()
        return response_payload
    except Exception:
        fail_idempotent_request(db, start=idem)
        db.commit()
        raise
