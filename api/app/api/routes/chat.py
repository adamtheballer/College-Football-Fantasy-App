from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, get_league_or_404
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.chat import (
    LeagueChatReadState,
    LeagueChatReadUpdate,
    LeagueMessageCreate,
    LeagueMessageList,
    LeagueMessageRead,
    LeagueMessageReportCreate,
    LeagueMessageReportRead,
    LeagueMessageUpdate,
)
from collegefootballfantasy_api.app.services.chat_service import (
    create_message,
    delete_message,
    list_messages,
    mark_chat_read,
    report_message,
    update_message,
)

router = APIRouter()


@router.get("/leagues/{league_id}/chat/messages", response_model=LeagueMessageList)
def get_league_chat_messages(
    league_id: int,
    limit: int = 50,
    before_id: int | None = None,
    after_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueMessageList:
    league = get_league_or_404(db, league_id)
    return list_messages(
        db,
        league=league,
        current_user=current_user,
        limit=limit,
        before_id=before_id,
        after_id=after_id,
    )


@router.post("/leagues/{league_id}/chat/messages", response_model=LeagueMessageRead, status_code=status.HTTP_201_CREATED)
def post_league_chat_message(
    league_id: int,
    payload: LeagueMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueMessageRead:
    league = get_league_or_404(db, league_id)
    return create_message(db, league=league, payload=payload, current_user=current_user)


@router.patch("/leagues/{league_id}/chat/messages/{message_id}", response_model=LeagueMessageRead)
def patch_league_chat_message(
    league_id: int,
    message_id: int,
    payload: LeagueMessageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueMessageRead:
    league = get_league_or_404(db, league_id)
    return update_message(db, league=league, message_id=message_id, payload=payload, current_user=current_user)


@router.delete("/leagues/{league_id}/chat/messages/{message_id}", response_model=LeagueMessageRead)
def delete_league_chat_message(
    league_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueMessageRead:
    league = get_league_or_404(db, league_id)
    return delete_message(db, league=league, message_id=message_id, current_user=current_user)


@router.post("/leagues/{league_id}/chat/messages/{message_id}/report", response_model=LeagueMessageReportRead, status_code=status.HTTP_201_CREATED)
def report_league_chat_message(
    league_id: int,
    message_id: int,
    payload: LeagueMessageReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueMessageReportRead:
    league = get_league_or_404(db, league_id)
    return report_message(db, league=league, message_id=message_id, payload=payload, current_user=current_user)


@router.post("/leagues/{league_id}/chat/read", response_model=LeagueChatReadState)
def mark_league_chat_read(
    league_id: int,
    payload: LeagueChatReadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueChatReadState:
    league = get_league_or_404(db, league_id)
    return mark_chat_read(db, league=league, payload=payload, current_user=current_user)
