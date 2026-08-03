from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, get_optional_current_user, require_admin_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.saturday_pick import (
    SaturdayPickContestCreate,
    SaturdayPickContestPublish,
    SaturdayPickContestRead,
    SaturdayPickEntryRead,
    SaturdayPickEntryWrite,
)
from collegefootballfantasy_api.app.services import saturday_pick_service


router = APIRouter()
admin_router = APIRouter()


def _require_feature() -> None:
    if not settings.saturday_pick_6_enabled or not settings.saturday_pick_6_public_enabled:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saturday Pick 6 is unavailable")


@router.get("/current", response_model=SaturdayPickContestRead)
def current_contest_endpoint(
    season: int = 2026,
    week: int = 1,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> SaturdayPickContestRead:
    _require_feature()
    contest = saturday_pick_service.current_contest(db, season, week)
    return saturday_pick_service.serialize_contest(db, contest, current_user)


@router.put("/{contest_id}/entry", response_model=SaturdayPickEntryRead)
def save_entry_endpoint(
    contest_id: int,
    payload: SaturdayPickEntryWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SaturdayPickEntryRead:
    _require_feature()
    contest = saturday_pick_service.get_contest_or_404(db, contest_id)
    entry = saturday_pick_service.save_entry(db, contest, payload.selected_pick_player_id, current_user)
    return saturday_pick_service._entry_read(entry)


@router.delete("/{contest_id}/entry", status_code=status.HTTP_204_NO_CONTENT)
def clear_entry_endpoint(
    contest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Forget a manager's current selection before they choose and lock a replacement."""
    _require_feature()
    contest = saturday_pick_service.get_contest_or_404(db, contest_id)
    saturday_pick_service.clear_entry(db, contest, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post("", response_model=SaturdayPickContestRead, status_code=status.HTTP_201_CREATED)
def create_contest_endpoint(
    payload: SaturdayPickContestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickContestRead:
    contest = saturday_pick_service.create_contest(db, payload, current_user)
    return saturday_pick_service.serialize_contest(db, contest, current_user)


@admin_router.post("/{contest_id}/publish", response_model=SaturdayPickContestRead)
def publish_contest_endpoint(
    contest_id: int,
    payload: SaturdayPickContestPublish,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickContestRead:
    contest = saturday_pick_service.get_contest_or_404(db, contest_id)
    contest = saturday_pick_service.publish_contest(db, contest, payload.lock_at)
    return saturday_pick_service.serialize_contest(db, contest, current_user)
