from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.scoring_job_lock import ScoringJobLock
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.services.scoring_service import ScoringSummary, recalculate_league_week_scores


ProviderSyncFn = Callable[[], dict[str, Any]]
SleepFn = Callable[[float], None]


class ProviderSyncFailed(RuntimeError):
    def __init__(self, message: str, retry_count: int, latency_ms: int):
        super().__init__(message)
        self.retry_count = retry_count
        self.latency_ms = latency_ms


class ProviderDataValidationFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 2.0
    max_backoff_seconds: float = 30.0


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    lock_acquired: bool
    run_id: int | None = None
    players_updated: int = 0
    teams_updated: int = 0
    matchups_updated: int = 0
    standings_updated: int = 0
    retry_count: int = 0
    message: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def scoring_lock_key(provider: str, season: int, week: int, league_id: int | None) -> str:
    scope = league_id if league_id is not None else "all"
    return f"scoring:{season}:{week}:{scope}"


def acquire_scoring_lock(
    db: Session,
    *,
    provider: str,
    season: int,
    week: int,
    league_id: int | None,
    worker_id: str,
    ttl_seconds: int = 300,
    now: datetime | None = None,
) -> ScoringJobLock | None:
    timestamp = now or _now()
    lock_key = scoring_lock_key(provider, season, week, league_id)
    lock = (
        db.query(ScoringJobLock)
        .filter(ScoringJobLock.lock_key == lock_key)
        .with_for_update()
        .first()
    )
    expires_at = timestamp + timedelta(seconds=ttl_seconds)
    if lock:
        if lock.status == "active" and _aware(lock.expires_at) > timestamp:
            return None
        lock.provider = provider
        lock.league_id = league_id
        lock.season = season
        lock.week = week
        lock.status = "active"
        lock.worker_id = worker_id
        lock.acquired_at = timestamp
        lock.heartbeat_at = timestamp
        lock.expires_at = expires_at
        db.flush()
        return lock

    lock = ScoringJobLock(
        lock_key=lock_key,
        provider=provider,
        league_id=league_id,
        season=season,
        week=week,
        status="active",
        worker_id=worker_id,
        acquired_at=timestamp,
        heartbeat_at=timestamp,
        expires_at=expires_at,
    )
    db.add(lock)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None
    return lock


def heartbeat_scoring_lock(
    db: Session,
    lock: ScoringJobLock,
    *,
    ttl_seconds: int = 300,
    now: datetime | None = None,
) -> None:
    timestamp = now or _now()
    lock.heartbeat_at = timestamp
    lock.expires_at = timestamp + timedelta(seconds=ttl_seconds)
    db.flush()


def release_scoring_lock(
    db: Session,
    lock: ScoringJobLock,
    *,
    status: str = "released",
    now: datetime | None = None,
) -> None:
    timestamp = now or _now()
    lock.status = status
    lock.heartbeat_at = timestamp
    lock.expires_at = timestamp
    db.flush()


def _commit_lock_state(db: Session, lock: ScoringJobLock) -> ScoringJobLock:
    lock_id = lock.id
    db.commit()
    refreshed = db.get(ScoringJobLock, lock_id)
    if refreshed is None:
        raise RuntimeError("scoring lock disappeared after commit")
    return refreshed


def recover_stale_scoring_runs(
    db: Session,
    *,
    older_than_seconds: int = 900,
    now: datetime | None = None,
) -> int:
    timestamp = now or _now()
    cutoff = timestamp - timedelta(seconds=older_than_seconds)
    rows = (
        db.query(ScoringRun)
        .filter(ScoringRun.status == "running", ScoringRun.started_at < cutoff)
        .all()
    )
    for row in rows:
        row.status = "failed"
        row.completed_at = timestamp
        row.error_message = "stale scoring run recovered"
    if rows:
        db.flush()
    return len(rows)


def _latest_successful_run_id(
    db: Session,
    *,
    provider: str,
    season: int,
    week: int,
    league_id: int | None,
) -> int | None:
    row = (
        db.query(ScoringRun)
        .filter(
            ScoringRun.provider == provider,
            ScoringRun.season == season,
            ScoringRun.week == week,
            ScoringRun.league_id == league_id,
            ScoringRun.status == "success",
        )
        .order_by(ScoringRun.completed_at.desc().nullslast(), ScoringRun.id.desc())
        .first()
    )
    return row.id if row else None


def _run_with_retry(
    operation: ProviderSyncFn,
    *,
    retry_policy: RetryPolicy,
    sleeper: SleepFn,
) -> tuple[dict[str, Any], int, int]:
    attempts = 0
    started_at = time.monotonic()
    while True:
        attempts += 1
        try:
            result = operation()
            latency_ms = int((time.monotonic() - started_at) * 1000)
            return result, attempts - 1, latency_ms
        except Exception:
            if attempts >= retry_policy.max_attempts:
                latency_ms = int((time.monotonic() - started_at) * 1000)
                raise ProviderSyncFailed("provider sync failed", attempts - 1, latency_ms)
            delay = min(
                retry_policy.max_backoff_seconds,
                retry_policy.initial_backoff_seconds * (2 ** (attempts - 1)),
            )
            sleeper(delay)


def _int_result(result: dict[str, Any], key: str) -> int:
    try:
        return int(result.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _result_allows_empty_data(result: dict[str, Any]) -> bool:
    return bool(result.get("allow_empty"))


def _has_league_matchups(db: Session, *, season: int, week: int, league_id: int | None) -> bool:
    from collegefootballfantasy_api.app.models.matchup import Matchup

    league_ids = _target_league_ids(db, season=season, league_id=league_id)
    if not league_ids:
        return False
    return (
        db.query(Matchup.id)
        .filter(
            Matchup.league_id.in_(league_ids),
            Matchup.season == season,
            Matchup.week == week,
        )
        .first()
        is not None
    )


def validate_provider_sync_result(
    db: Session,
    result: dict[str, Any],
    *,
    season: int,
    week: int,
    league_id: int | None,
) -> None:
    if _result_allows_empty_data(result):
        return
    rows_seen = _int_result(result, "rows_seen")
    events_seen = _int_result(result, "events")
    if rows_seen > 0 or events_seen > 0:
        return
    if _has_league_matchups(db, season=season, week=week, league_id=league_id):
        raise ProviderDataValidationFailed(
            "provider returned zero stat rows/events for a league week with matchups; preserving existing scores"
        )


def _target_league_ids(db: Session, *, season: int, league_id: int | None) -> list[int]:
    if league_id is not None:
        if not db.get(League, league_id):
            raise ValueError(f"league {league_id} not found")
        return [league_id]
    return [
        row.id
        for row in db.query(League).filter(League.season_year == season).order_by(League.id.asc()).all()
    ]


def run_scoring_worker_once(
    db: Session,
    *,
    provider: str,
    season: int,
    week: int,
    league_id: int | None,
    sync_provider_stats: ProviderSyncFn,
    retry_policy: RetryPolicy | None = None,
    lock_ttl_seconds: int = 300,
    stale_run_seconds: int = 900,
    worker_id: str | None = None,
    sleeper: SleepFn = time.sleep,
) -> WorkerRunResult:
    retry_policy = retry_policy or RetryPolicy()
    worker_id = worker_id or f"scoring-worker-{uuid.uuid4()}"
    recover_stale_scoring_runs(db, older_than_seconds=stale_run_seconds)
    db.commit()
    lock = acquire_scoring_lock(
        db,
        provider=provider,
        season=season,
        week=week,
        league_id=league_id,
        worker_id=worker_id,
        ttl_seconds=lock_ttl_seconds,
    )
    if not lock:
        db.commit()
        return WorkerRunResult(status="skipped", lock_acquired=False, message="scoring job already running")
    lock = _commit_lock_state(db, lock)

    run = ScoringRun(
        league_id=league_id,
        season=season,
        week=week,
        provider=provider,
        status="running",
        started_at=_now(),
        lock_key=lock.lock_key,
        worker_id=worker_id,
        last_successful_run_id=_latest_successful_run_id(
            db,
            provider=provider,
            season=season,
            week=week,
            league_id=league_id,
        ),
    )
    db.add(run)
    db.flush()
    run_id = run.id
    db.commit()
    run = db.get(ScoringRun, run_id)
    lock = db.get(ScoringJobLock, lock.id)
    if run is None or lock is None:
        raise RuntimeError("scoring worker state disappeared after commit")

    try:
        run.data_started_at = _now()
        db.commit()
        run = db.get(ScoringRun, run_id)
        lock = db.get(ScoringJobLock, lock.id)
        if run is None or lock is None:
            raise RuntimeError("scoring worker state disappeared before provider sync")
        sync_result, retry_count, latency_ms = _run_with_retry(
            sync_provider_stats,
            retry_policy=retry_policy,
            sleeper=sleeper,
        )
        validate_provider_sync_result(db, sync_result, season=season, week=week, league_id=league_id)
        run.data_completed_at = _now()
        run.provider_latency_ms = latency_ms
        run.retry_count = retry_count
        run.rows_fetched = _int_result(sync_result, "rows_seen")
        run.rows_matched = _int_result(sync_result, "upserted")
        run.rows_unmatched = _int_result(sync_result, "skipped")
        run.provider_events_seen = _int_result(sync_result, "events")
        run.data_age_seconds = _int_result(sync_result, "data_age_seconds") if "data_age_seconds" in sync_result else None
        db.commit()
        run = db.get(ScoringRun, run_id)
        lock = db.get(ScoringJobLock, lock.id)
        if run is None or lock is None:
            raise RuntimeError("scoring worker state disappeared after provider sync")

        totals = ScoringSummary(0, 0, 0, 0)
        for target_league_id in _target_league_ids(db, season=season, league_id=league_id):
            heartbeat_scoring_lock(db, lock, ttl_seconds=lock_ttl_seconds)
            lock = _commit_lock_state(db, lock)
            run = db.get(ScoringRun, run_id)
            if run is None:
                raise RuntimeError("scoring run disappeared during heartbeat")
            current = recalculate_league_week_scores(db, target_league_id, season, week)
            totals = ScoringSummary(
                players_scored=totals.players_scored + current.players_scored,
                teams_scored=totals.teams_scored + current.teams_scored,
                matchups_updated=totals.matchups_updated + current.matchups_updated,
                standings_updated=totals.standings_updated + current.standings_updated,
            )

        run.status = "success"
        run.completed_at = _now()
        run.players_updated = totals.players_scored
        run.teams_updated = totals.teams_scored
        run.matchups_updated = totals.matchups_updated
        release_scoring_lock(db, lock)
        db.commit()
        return WorkerRunResult(
            status="success",
            lock_acquired=True,
            run_id=run.id,
            players_updated=totals.players_scored,
            teams_updated=totals.teams_scored,
            matchups_updated=totals.matchups_updated,
            standings_updated=totals.standings_updated,
            retry_count=run.retry_count,
        )
    except (ProviderSyncFailed, ProviderDataValidationFailed) as exc:
        if isinstance(exc, ProviderSyncFailed):
            run.retry_count = exc.retry_count
            run.provider_latency_ms = exc.latency_ms
        run.status = "failed"
        run.completed_at = _now()
        run.error_message = str(exc)[:1000]
        release_scoring_lock(db, lock, status="released")
        db.commit()
        raise
    except Exception as exc:
        run.status = "failed"
        run.completed_at = _now()
        run.error_message = str(exc)[:1000]
        release_scoring_lock(db, lock, status="released")
        db.commit()
        raise
