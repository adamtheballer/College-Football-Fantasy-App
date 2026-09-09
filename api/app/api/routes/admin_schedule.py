from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.schedule_sync_issue import ScheduleSyncIssue
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.admin_schedule import (
    AdminScheduleIssueRead,
    AdminScheduleManualOverrideRequest,
    AdminScheduleManualOverrideResponse,
    AdminScheduleSyncRequest,
    AdminScheduleSyncResponse,
)
from collegefootballfantasy_api.app.services.schedule_time_sync import (
    apply_manual_kickoff_override,
    resolve_schedule_sync_source,
    sync_schedule_times,
)


router = APIRouter()


@router.post("/sync", response_model=AdminScheduleSyncResponse)
def sync_schedule_endpoint(
    payload: AdminScheduleSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> dict:
    """Manually perform a guarded schedule-time reconciliation now."""

    source = resolve_schedule_sync_source() if payload.source == "auto" else payload.source
    if source == "sportsdata" and (not settings.sportsdata_enabled or not settings.sportsdata_api_key):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SportsData schedule sync is not configured")
    try:
        summary = sync_schedule_times(
            db,
            season=payload.season_year,
            week=payload.week,
            source=source,
            force_current_week=payload.force_current_week,
            actor_user_id=current_user.id,
        )
        db.commit()
        return summary.as_dict()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="schedule sync failed; no changes were committed") from exc


@router.get("/issues", response_model=list[AdminScheduleIssueRead])
def list_schedule_issues(
    season_year: int | None = Query(default=None, ge=2000, le=2100),
    week: int | None = Query(default=None, ge=0, le=20),
    include_resolved: bool = False,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin_user),
) -> list[ScheduleSyncIssue]:
    statement = select(ScheduleSyncIssue).order_by(ScheduleSyncIssue.updated_at.desc(), ScheduleSyncIssue.id.desc())
    if season_year is not None:
        statement = statement.where(ScheduleSyncIssue.season == season_year)
    if week is not None:
        statement = statement.where(ScheduleSyncIssue.week == week)
    if not include_resolved:
        statement = statement.where(ScheduleSyncIssue.resolved_at.is_(None))
    return list(db.scalars(statement))


@router.put("/{schedule_id}/kickoff", response_model=AdminScheduleManualOverrideResponse)
def manual_schedule_kickoff_override(
    schedule_id: int,
    payload: AdminScheduleManualOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> TeamSchedule:
    try:
        row = apply_manual_kickoff_override(
            db, schedule_id=schedule_id, kickoff_at=payload.kickoff_at, reason=payload.reason.strip(), actor_user_id=current_user.id,
        )
        db.commit()
        db.refresh(row)
        return row
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
