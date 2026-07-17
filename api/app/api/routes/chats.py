from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, get_league_or_404
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.chat import (
    ChatDirectThreadCreate,
    ChatMessageCreate,
    ChatMessageEdit,
    ChatMessagePage,
    ChatMessageRead,
    ChatReadReceipt,
    ChatReadStateUpdate,
    ChatThreadList,
    ChatThreadRead,
    ChatUnreadSummary,
)
from collegefootballfantasy_api.app.services.chat_service import (
    create_or_get_direct_thread,
    create_user_message,
    delete_user_message,
    edit_user_message,
    list_league_threads,
    list_thread_messages,
    list_unread_summary,
    mark_thread_read,
)


league_router = APIRouter(prefix="/leagues/{league_id}/chats")
router = APIRouter(prefix="/chats")


@league_router.get("", response_model=ChatThreadList)
def list_threads_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatThreadList:
    get_league_or_404(db, league_id)
    return list_league_threads(db, league_id=league_id, current_user=current_user)


@league_router.post("/direct", response_model=ChatThreadRead, status_code=status.HTTP_201_CREATED)
def create_direct_thread_endpoint(
    league_id: int,
    payload: ChatDirectThreadCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatThreadRead:
    get_league_or_404(db, league_id)
    return create_or_get_direct_thread(
        db,
        request=request,
        league_id=league_id,
        current_user=current_user,
        payload=payload,
    )


@league_router.get("/{thread_id}/messages", response_model=ChatMessagePage)
def list_messages_endpoint(
    league_id: int,
    thread_id: int,
    before_message_id: int | None = Query(default=None, gt=0),
    after_message_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessagePage:
    get_league_or_404(db, league_id)
    return list_thread_messages(
        db,
        league_id=league_id,
        thread_id=thread_id,
        current_user=current_user,
        before_message_id=before_message_id,
        after_message_id=after_message_id,
        limit=limit,
    )


@league_router.post("/{thread_id}/messages", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
def create_message_endpoint(
    league_id: int,
    thread_id: int,
    payload: ChatMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessageRead:
    get_league_or_404(db, league_id)
    return create_user_message(
        db,
        request=request,
        league_id=league_id,
        thread_id=thread_id,
        current_user=current_user,
        payload=payload,
    )


@league_router.patch("/{thread_id}/messages/{message_id}", response_model=ChatMessageRead)
def edit_message_endpoint(
    league_id: int,
    thread_id: int,
    message_id: int,
    payload: ChatMessageEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessageRead:
    get_league_or_404(db, league_id)
    return edit_user_message(
        db,
        league_id=league_id,
        thread_id=thread_id,
        message_id=message_id,
        current_user=current_user,
        payload=payload,
    )


@league_router.delete("/{thread_id}/messages/{message_id}", response_model=ChatMessageRead)
def delete_message_endpoint(
    league_id: int,
    thread_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessageRead:
    get_league_or_404(db, league_id)
    return delete_user_message(
        db,
        league_id=league_id,
        thread_id=thread_id,
        message_id=message_id,
        current_user=current_user,
    )


@league_router.post("/{thread_id}/read", response_model=ChatReadReceipt)
def mark_thread_read_endpoint(
    league_id: int,
    thread_id: int,
    payload: ChatReadStateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatReadReceipt:
    get_league_or_404(db, league_id)
    return mark_thread_read(
        db,
        request=request,
        league_id=league_id,
        thread_id=thread_id,
        current_user=current_user,
        payload=payload,
    )


@router.get("/unread-summary", response_model=ChatUnreadSummary)
def unread_summary_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatUnreadSummary:
    return list_unread_summary(db, current_user=current_user)
