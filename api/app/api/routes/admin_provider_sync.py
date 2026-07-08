from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.provider_sync_job import ProviderSyncJob
from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.provider_stats_service import sync_provider_weekly_player_stats

router = APIRouter()


class ProviderSyncRunRequest(BaseModel):
    provider: str
    feed: str = "player_game_stats_week"
    season: int
    week: int


def _is_stale(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def _state_row(state: ProviderSyncState) -> dict:
    return {
        "id": state.id,
        "provider": state.provider,
        "feed": state.feed,
        "scope_key": state.scope_key,
        "status": state.status,
        "is_stale": _is_stale(state.expires_at),
        "last_attempted_at": state.last_attempted_at,
        "last_successful_sync_at": state.last_success_at,
        "source_updated_at": state.updated_at,
        "cache_expires_at": state.expires_at,
        "error_message": state.error_message,
        "consecutive_failures": state.consecutive_failures,
        "metadata": state.meta,
    }


def _job_row(job: ProviderSyncJob) -> dict:
    return {
        "id": job.id,
        "provider": job.provider,
        "feed": job.feed,
        "season": job.season,
        "week": job.week,
        "scope": job.scope,
        "status": job.status,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "rows_seen": job.rows_seen,
        "rows_inserted": job.rows_inserted,
        "rows_updated": job.rows_updated,
        "rows_rejected": job.rows_rejected,
        "error_summary": job.error_summary,
    }


@router.get("/status")
def provider_sync_status(
    provider: str | None = None,
    feed: str | None = None,
    season: int | None = None,
    week: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    states_query = db.query(ProviderSyncState)
    jobs_query = db.query(ProviderSyncJob)
    if provider:
        states_query = states_query.filter(ProviderSyncState.provider == provider)
        jobs_query = jobs_query.filter(ProviderSyncJob.provider == provider)
    if feed:
        states_query = states_query.filter(ProviderSyncState.feed == feed)
        jobs_query = jobs_query.filter(ProviderSyncJob.feed == feed)
    if season is not None:
        jobs_query = jobs_query.filter(ProviderSyncJob.season == season)
    if week is not None:
        jobs_query = jobs_query.filter(ProviderSyncJob.week == week)
    states = states_query.order_by(ProviderSyncState.provider.asc(), ProviderSyncState.feed.asc()).all()
    jobs = (
        jobs_query.order_by(ProviderSyncJob.started_at.desc(), ProviderSyncJob.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return {
        "states": [_state_row(state) for state in states],
        "recent_jobs": [_job_row(job) for job in jobs],
    }


@router.post("/run")
def run_provider_sync(
    payload: ProviderSyncRunRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    if payload.feed != "player_game_stats_week":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="only player_game_stats_week sync is supported from this endpoint",
        )
    try:
        result = sync_provider_weekly_player_stats(
            db,
            provider=payload.provider,
            season=payload.season,
            week=payload.week,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {
        "provider": payload.provider,
        "feed": payload.feed,
        "season": payload.season,
        "week": payload.week,
        "result": result,
    }
