from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.moderation_event import ModerationEvent
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.admin_moderation import ModerationEventList, ModerationEventRead


router = APIRouter()


@router.get("/events", response_model=ModerationEventList)
def list_moderation_events(
    field_name: str | None = Query(default=None, max_length=80),
    reason_code: str | None = Query(default=None, max_length=80),
    league_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin_user),
) -> ModerationEventList:
    query = db.query(ModerationEvent)
    count_query = db.query(func.count(ModerationEvent.id))
    if field_name:
        query = query.filter(ModerationEvent.field_name == field_name)
        count_query = count_query.filter(ModerationEvent.field_name == field_name)
    if reason_code:
        query = query.filter(ModerationEvent.reason_code == reason_code)
        count_query = count_query.filter(ModerationEvent.reason_code == reason_code)
    if league_id is not None:
        query = query.filter(ModerationEvent.league_id == league_id)
        count_query = count_query.filter(ModerationEvent.league_id == league_id)
    rows = (
        query.order_by(ModerationEvent.created_at.desc(), ModerationEvent.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ModerationEventList(
        data=[ModerationEventRead.model_validate(row) for row in rows],
        total=count_query.scalar() or 0,
        limit=limit,
        offset=offset,
    )
