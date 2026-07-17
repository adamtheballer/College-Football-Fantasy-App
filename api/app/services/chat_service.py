from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_league_membership
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.chat import (
    ChatAuditEvent,
    ChatMessage,
    ChatReadState,
    ChatThread,
    ChatThreadParticipant,
)
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.chat import (
    ChatDirectThreadCreate,
    ChatMessageCreate,
    ChatMessageEdit,
    ChatMessagePage,
    ChatMessagePreview,
    ChatMessageRead,
    ChatParticipantRead,
    ChatReadStateUpdate,
    ChatThreadList,
    ChatThreadRead,
    ChatReadReceipt,
    ChatUnreadLeagueRead,
    ChatUnreadSummary,
)
from collegefootballfantasy_api.app.services.auth_security import enforce_auth_rate_limit


SYSTEM_MESSAGE_TYPES = {
    "system",
    "trade_finalized",
    "trade_processed",
    "waiver",
    "draft",
    "commissioner",
}
MASTER_LEAGUE_THREAD_TITLE = "General"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _enforce_chat_rate_limit(
    db: Session,
    *,
    action: str,
    current_user: User,
    request: Request,
    limit: int,
    window_minutes: int,
) -> None:
    try:
        enforce_auth_rate_limit(
            db,
            action=action,
            identifier=str(current_user.id),
            request=request,
            limit=limit,
            window_minutes=window_minutes,
            include_ip=False,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many chat requests. Please wait and try again.",
            ) from exc
        raise


def _record_chat_audit_event(
    db: Session,
    *,
    league_id: int,
    action: str,
    actor_user_id: int | None = None,
    thread_id: int | None = None,
    message_id: int | None = None,
    metadata_json: dict | None = None,
    event_key: str | None = None,
) -> ChatAuditEvent:
    if event_key:
        existing = db.query(ChatAuditEvent).filter(ChatAuditEvent.event_key == event_key).one_or_none()
        if existing:
            return existing
    try:
        with db.begin_nested():
            audit = ChatAuditEvent(
                league_id=league_id,
                thread_id=thread_id,
                message_id=message_id,
                actor_user_id=actor_user_id,
                action=action,
                metadata_json=metadata_json or {},
                event_key=event_key,
            )
            db.add(audit)
            db.flush()
    except IntegrityError:
        if event_key:
            existing = db.query(ChatAuditEvent).filter(ChatAuditEvent.event_key == event_key).one_or_none()
            if existing:
                return existing
        raise
    return audit


def _require_league_membership(db: Session, *, league_id: int, user_id: int) -> None:
    if not get_league_membership(db, league_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="league membership required")


def get_or_create_league_chat_thread(db: Session, league_id: int) -> ChatThread:
    """Return the single master thread for a league without duplicate creation races."""
    thread = (
        db.query(ChatThread)
        .filter(ChatThread.league_id == league_id, ChatThread.thread_type == "league")
        .one_or_none()
    )
    if thread:
        if not thread.title:
            thread.title = MASTER_LEAGUE_THREAD_TITLE
        return thread

    try:
        with db.begin_nested():
            thread = ChatThread(
                league_id=league_id,
                thread_type="league",
                title=MASTER_LEAGUE_THREAD_TITLE,
            )
            db.add(thread)
            db.flush()
    except IntegrityError:
        thread = (
            db.query(ChatThread)
            .filter(ChatThread.league_id == league_id, ChatThread.thread_type == "league")
            .one_or_none()
        )
        if thread:
            return thread
        raise
    return thread


def _require_thread_access(db: Session, *, league_id: int, thread_id: int, user_id: int) -> ChatThread:
    _require_league_membership(db, league_id=league_id, user_id=user_id)
    thread = (
        db.query(ChatThread)
        .filter(ChatThread.id == thread_id, ChatThread.league_id == league_id)
        .one_or_none()
    )
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat thread not found")
    if thread.is_archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="chat thread is archived")
    if thread.thread_type == "direct":
        participant = (
            db.query(ChatThreadParticipant)
            .filter(
                ChatThreadParticipant.thread_id == thread.id,
                ChatThreadParticipant.user_id == user_id,
                ChatThreadParticipant.left_at.is_(None),
            )
            .first()
        )
        if not participant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat thread not found")
    return thread


def _thread_unread_counts(db: Session, *, thread_ids: list[int], user_id: int) -> dict[int, int]:
    if not thread_ids:
        return {}
    rows = (
        db.query(ChatMessage.thread_id, func.count(ChatMessage.id))
        .outerjoin(
            ChatReadState,
            and_(
                ChatReadState.thread_id == ChatMessage.thread_id,
                ChatReadState.user_id == user_id,
            ),
        )
        .filter(ChatMessage.thread_id.in_(thread_ids))
        .filter(ChatMessage.deleted_at.is_(None))
        .filter(or_(ChatMessage.sender_user_id.is_(None), ChatMessage.sender_user_id != user_id))
        .filter(
            or_(
                ChatReadState.last_read_message_id.is_(None),
                ChatMessage.id > ChatReadState.last_read_message_id,
            )
        )
        .group_by(ChatMessage.thread_id)
        .all()
    )
    return {thread_id: int(count) for thread_id, count in rows}


def _participant_display_name(user: User) -> str:
    return user.first_name or user.username or f"Manager #{user.id}"


def _participant_reads_by_thread(db: Session, *, thread_ids: list[int]) -> dict[int, list[ChatParticipantRead]]:
    participant_reads: dict[int, list[ChatParticipantRead]] = {thread_id: [] for thread_id in thread_ids}
    if not thread_ids:
        return participant_reads

    rows = (
        db.query(ChatThreadParticipant, User, Team)
        .join(User, User.id == ChatThreadParticipant.user_id)
        .join(ChatThread, ChatThread.id == ChatThreadParticipant.thread_id)
        .outerjoin(
            Team,
            and_(
                Team.league_id == ChatThread.league_id,
                Team.owner_user_id == ChatThreadParticipant.user_id,
            ),
        )
        .filter(ChatThreadParticipant.thread_id.in_(thread_ids), ChatThreadParticipant.left_at.is_(None))
        .order_by(ChatThreadParticipant.thread_id, ChatThreadParticipant.id)
        .all()
    )
    for participant, user, team in rows:
        participant_reads[participant.thread_id].append(
            ChatParticipantRead(
                user_id=participant.user_id,
                joined_at=participant.joined_at,
                display_name=_participant_display_name(user),
                fantasy_team_name=team.name if team else None,
            )
        )

    # League chat access is derived from active league membership, so master
    # threads do not need one participant row per member to render a member list.
    master_threads = (
        db.query(ChatThread.id, ChatThread.league_id)
        .filter(ChatThread.id.in_(thread_ids), ChatThread.thread_type == "league")
        .all()
    )
    for thread_id, league_id in master_threads:
        member_rows = (
            db.query(LeagueMember, User, Team)
            .join(User, User.id == LeagueMember.user_id)
            .outerjoin(Team, and_(Team.league_id == LeagueMember.league_id, Team.owner_user_id == LeagueMember.user_id))
            .filter(LeagueMember.league_id == league_id)
            .order_by(LeagueMember.joined_at, LeagueMember.id)
            .all()
        )
        participant_reads[thread_id] = [
            ChatParticipantRead(
                user_id=member.user_id,
                joined_at=member.joined_at,
                display_name=_participant_display_name(user),
                fantasy_team_name=team.name if team else None,
            )
            for member, user, team in member_rows
        ]
    return participant_reads


def _latest_messages_by_thread(db: Session, *, thread_ids: list[int]) -> dict[int, ChatMessage]:
    if not thread_ids:
        return {}
    latest_message_ids = (
        db.query(ChatMessage.thread_id, func.max(ChatMessage.id).label("message_id"))
        .filter(ChatMessage.thread_id.in_(thread_ids), ChatMessage.deleted_at.is_(None))
        .group_by(ChatMessage.thread_id)
        .subquery()
    )
    rows = (
        db.query(ChatMessage)
        .join(latest_message_ids, ChatMessage.id == latest_message_ids.c.message_id)
        .all()
    )
    return {message.thread_id: message for message in rows}


def _preview_text(message: ChatMessage | None) -> str | None:
    if not message:
        return None
    if message.body:
        return message.body[:160]
    return message.message_type.replace("_", " ").title()


def _thread_read(
    thread: ChatThread,
    *,
    unread_count: int,
    participants: list[ChatParticipantRead],
    current_user_id: int,
    last_message: ChatMessage | None,
) -> ChatThreadRead:
    other_participant = next(
        (participant for participant in participants if participant.user_id != current_user_id),
        None,
    )
    return ChatThreadRead(
        id=thread.id,
        league_id=thread.league_id,
        thread_type=thread.thread_type,
        title=thread.title,
        created_by_user_id=thread.created_by_user_id,
        direct_user_low_id=thread.direct_user_low_id,
        direct_user_high_id=thread.direct_user_high_id,
        is_archived=thread.is_archived,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        participants=participants,
        other_participant=other_participant if thread.thread_type == "direct" else None,
        last_message_preview=_preview_text(last_message),
        last_message_at=last_message.created_at if last_message else None,
        unread_count=unread_count,
    )


def _user_profiles(db: Session, *, league_id: int, user_ids: set[int]) -> dict[int, tuple[str, str | None]]:
    if not user_ids:
        return {}
    rows = (
        db.query(User, Team)
        .outerjoin(Team, and_(Team.league_id == league_id, Team.owner_user_id == User.id))
        .filter(User.id.in_(user_ids))
        .all()
    )
    return {
        user.id: (_participant_display_name(user), team.name if team else None)
        for user, team in rows
    }


def _message_reads(db: Session, messages: list[ChatMessage]) -> list[ChatMessageRead]:
    if not messages:
        return []
    reply_ids = {message.reply_to_message_id for message in messages if message.reply_to_message_id is not None}
    replies = (
        db.query(ChatMessage)
        .filter(ChatMessage.id.in_(reply_ids))
        .all()
        if reply_ids
        else []
    )
    reply_by_id = {reply.id: reply for reply in replies}
    user_ids = {
        user_id
        for message in [*messages, *replies]
        if (user_id := message.sender_user_id) is not None
    }
    profiles = _user_profiles(db, league_id=messages[0].league_id, user_ids=user_ids)
    results: list[ChatMessageRead] = []
    for message in messages:
        sender_display_name, sender_team_name = profiles.get(message.sender_user_id, (None, None))
        reply = reply_by_id.get(message.reply_to_message_id)
        reply_sender_name = profiles.get(reply.sender_user_id, (None, None))[0] if reply else None
        results.append(
            ChatMessageRead(
                id=message.id,
                thread_id=message.thread_id,
                league_id=message.league_id,
                sender_user_id=message.sender_user_id,
                message_type=message.message_type,
                body=None if message.deleted_at else message.body,
                metadata=message.metadata_json,
                client_message_id=message.client_message_id,
                reply_to_message_id=message.reply_to_message_id,
                edited_at=message.edited_at,
                deleted_at=message.deleted_at,
                created_at=message.created_at,
                updated_at=message.updated_at,
                sender_display_name=sender_display_name,
                sender_fantasy_team_name=sender_team_name,
                reply_to_message=(
                    ChatMessagePreview(
                        id=reply.id,
                        sender_display_name=reply_sender_name,
                        body=None if reply.deleted_at else reply.body,
                        message_type=reply.message_type,
                        created_at=reply.created_at,
                    )
                    if reply
                    else None
                ),
            )
        )
    return results


def _message_read(db: Session, message: ChatMessage) -> ChatMessageRead:
    return _message_reads(db, [message])[0]


def list_league_threads(db: Session, *, league_id: int, current_user: User) -> ChatThreadList:
    _require_league_membership(db, league_id=league_id, user_id=current_user.id)
    master_thread = get_or_create_league_chat_thread(db, league_id)
    # New leagues created before the migration runs are initialized lazily. Persist
    # the master thread before responding so the next request sees the same thread.
    db.commit()
    db.refresh(master_thread)
    threads = (
        db.query(ChatThread)
        .filter(ChatThread.league_id == league_id)
        .filter(
            or_(
                ChatThread.thread_type == "league",
                and_(
                    ChatThread.thread_type == "direct",
                    or_(
                        ChatThread.direct_user_low_id == current_user.id,
                        ChatThread.direct_user_high_id == current_user.id,
                    ),
                ),
            )
        )
        .order_by(ChatThread.thread_type.asc(), ChatThread.updated_at.desc(), ChatThread.id.desc())
        .all()
    )
    thread_ids = [thread.id for thread in threads]
    unread_counts = _thread_unread_counts(db, thread_ids=thread_ids, user_id=current_user.id)
    participants_by_thread = _participant_reads_by_thread(db, thread_ids=thread_ids)
    latest_messages = _latest_messages_by_thread(db, thread_ids=thread_ids)

    ordered_threads = sorted(
        threads,
        key=lambda thread: (
            0 if thread.thread_type == "league" else 1,
            -int((latest_messages.get(thread.id).created_at if latest_messages.get(thread.id) else thread.created_at).timestamp()),
            -thread.id,
        ),
    )

    return ChatThreadList(
        data=[
            _thread_read(
                thread,
                unread_count=unread_counts.get(thread.id, 0),
                participants=participants_by_thread.get(thread.id, []),
                current_user_id=current_user.id,
                last_message=latest_messages.get(thread.id),
            )
            for thread in ordered_threads
        ],
        total=len(threads),
    )


def create_or_get_direct_thread(
    db: Session,
    *,
    request: Request,
    league_id: int,
    current_user: User,
    payload: ChatDirectThreadCreate,
) -> ChatThreadRead:
    _require_league_membership(db, league_id=league_id, user_id=current_user.id)
    get_or_create_league_chat_thread(db, league_id)
    if payload.recipient_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="cannot direct message yourself")
    _require_league_membership(db, league_id=league_id, user_id=payload.recipient_user_id)

    low_user_id, high_user_id = sorted((current_user.id, payload.recipient_user_id))
    thread = (
        db.query(ChatThread)
        .filter(
            ChatThread.league_id == league_id,
            ChatThread.thread_type == "direct",
            ChatThread.direct_user_low_id == low_user_id,
            ChatThread.direct_user_high_id == high_user_id,
        )
        .one_or_none()
    )
    created = False
    if not thread:
        _enforce_chat_rate_limit(
            db,
            action="chat_direct_thread",
            current_user=current_user,
            request=request,
            limit=settings.chat_direct_thread_rate_limit,
            window_minutes=settings.chat_direct_thread_rate_limit_window_minutes,
        )
        try:
            with db.begin_nested():
                thread = ChatThread(
                    league_id=league_id,
                    thread_type="direct",
                    created_by_user_id=current_user.id,
                    direct_user_low_id=low_user_id,
                    direct_user_high_id=high_user_id,
                )
                db.add(thread)
                db.flush()
                db.add_all(
                    [
                        ChatThreadParticipant(thread_id=thread.id, user_id=low_user_id, joined_at=utcnow()),
                        ChatThreadParticipant(thread_id=thread.id, user_id=high_user_id, joined_at=utcnow()),
                    ]
                )
                db.flush()
                created = True
        except IntegrityError:
            thread = (
                db.query(ChatThread)
                .filter(
                    ChatThread.league_id == league_id,
                    ChatThread.thread_type == "direct",
                    ChatThread.direct_user_low_id == low_user_id,
                    ChatThread.direct_user_high_id == high_user_id,
                )
                .one_or_none()
            )
            if not thread:
                raise

    if created:
        _record_chat_audit_event(
            db,
            league_id=league_id,
            thread_id=thread.id,
            actor_user_id=current_user.id,
            action="direct_thread_created",
            metadata_json={"recipient_user_id": payload.recipient_user_id},
            event_key=f"direct-thread:{thread.id}:created",
        )

    db.commit()
    db.refresh(thread)
    participants = _participant_reads_by_thread(db, thread_ids=[thread.id])[thread.id]
    unread_count = _thread_unread_counts(db, thread_ids=[thread.id], user_id=current_user.id).get(thread.id, 0)
    latest_message = _latest_messages_by_thread(db, thread_ids=[thread.id]).get(thread.id)
    return _thread_read(
        thread,
        unread_count=unread_count,
        participants=participants,
        current_user_id=current_user.id,
        last_message=latest_message,
    )


def list_thread_messages(
    db: Session,
    *,
    league_id: int,
    thread_id: int,
    current_user: User,
    before_message_id: int | None,
    after_message_id: int | None,
    limit: int,
) -> ChatMessagePage:
    _require_thread_access(db, league_id=league_id, thread_id=thread_id, user_id=current_user.id)
    if before_message_id is not None and after_message_id is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="use one chat message cursor at a time")
    query = db.query(ChatMessage).filter(ChatMessage.thread_id == thread_id)
    if after_message_id is not None:
        rows = query.filter(ChatMessage.id > after_message_id).order_by(ChatMessage.id.asc()).limit(limit + 1).all()
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        return ChatMessagePage(
            data=_message_reads(db, page_rows),
            next_after_message_id=page_rows[-1].id if has_more and page_rows else None,
        )
    if before_message_id is not None:
        query = query.filter(ChatMessage.id < before_message_id)
    rows = query.order_by(ChatMessage.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    page_rows.reverse()
    return ChatMessagePage(
        data=_message_reads(db, page_rows),
        next_before_message_id=page_rows[0].id if has_more and page_rows else None,
    )


def create_user_message(
    db: Session,
    *,
    request: Request,
    league_id: int,
    thread_id: int,
    current_user: User,
    payload: ChatMessageCreate,
) -> ChatMessageRead:
    thread = _require_thread_access(db, league_id=league_id, thread_id=thread_id, user_id=current_user.id)
    if payload.client_message_id:
        existing = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.sender_user_id == current_user.id,
                ChatMessage.client_message_id == payload.client_message_id,
            )
            .one_or_none()
        )
        if existing:
            if existing.thread_id != thread_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="client message id already used")
            return _message_read(db, existing)

    _enforce_chat_rate_limit(
        db,
        action="chat_message",
        current_user=current_user,
        request=request,
        limit=settings.chat_message_rate_limit,
        window_minutes=settings.chat_message_rate_limit_window_minutes,
    )
    _enforce_chat_rate_limit(
        db,
        action="chat_message_sustained",
        current_user=current_user,
        request=request,
        limit=settings.chat_message_sustained_rate_limit,
        window_minutes=settings.chat_message_sustained_rate_limit_window_minutes,
    )
    if payload.reply_to_message_id is not None:
        reply_to = db.get(ChatMessage, payload.reply_to_message_id)
        if not reply_to or reply_to.thread_id != thread_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="reply must belong to this thread")

    message = ChatMessage(
        thread_id=thread.id,
        league_id=league_id,
        sender_user_id=current_user.id,
        message_type="user",
        body=payload.body,
        client_message_id=payload.client_message_id,
        reply_to_message_id=payload.reply_to_message_id,
        metadata_json={},
    )
    thread.updated_at = utcnow()
    db.add(message)
    db.add(thread)
    db.commit()
    db.refresh(message)
    return _message_read(db, message)


def _message_for_thread_or_404(db: Session, *, thread_id: int, message_id: int) -> ChatMessage:
    message = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == message_id, ChatMessage.thread_id == thread_id)
        .one_or_none()
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat message not found")
    return message


def _is_chat_moderator(db: Session, *, league_id: int, current_user: User) -> bool:
    membership = get_league_membership(db, league_id, current_user.id)
    league = db.get(League, league_id)
    return bool(
        membership
        and (
            current_user.is_admin
            or membership.role == "commissioner"
            or (league and league.commissioner_user_id == current_user.id)
        )
    )


def edit_user_message(
    db: Session,
    *,
    league_id: int,
    thread_id: int,
    message_id: int,
    current_user: User,
    payload: ChatMessageEdit,
) -> ChatMessageRead:
    thread = _require_thread_access(db, league_id=league_id, thread_id=thread_id, user_id=current_user.id)
    message = _message_for_thread_or_404(db, thread_id=thread.id, message_id=message_id)
    if message.message_type != "user" or message.sender_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only your user messages can be edited")
    if message.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deleted messages cannot be edited")
    if _as_utc(message.created_at) + timedelta(minutes=settings.chat_edit_window_minutes) < utcnow():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="message edit window has expired")
    message.body = payload.body
    message.edited_at = utcnow()
    thread.updated_at = utcnow()
    db.add_all((message, thread))
    db.commit()
    db.refresh(message)
    return _message_read(db, message)


def delete_user_message(
    db: Session,
    *,
    league_id: int,
    thread_id: int,
    message_id: int,
    current_user: User,
) -> ChatMessageRead:
    thread = _require_thread_access(db, league_id=league_id, thread_id=thread_id, user_id=current_user.id)
    message = _message_for_thread_or_404(db, thread_id=thread.id, message_id=message_id)
    if message.message_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="system messages cannot be deleted")
    is_owner = message.sender_user_id == current_user.id
    is_moderator = _is_chat_moderator(db, league_id=league_id, current_user=current_user)
    if not is_owner and not is_moderator:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="message deletion is not allowed")
    if message.deleted_at is None:
        message.deleted_at = utcnow()
        thread.updated_at = utcnow()
        db.add_all((message, thread))
        _record_chat_audit_event(
            db,
            league_id=league_id,
            thread_id=thread.id,
            message_id=message.id,
            actor_user_id=current_user.id,
            action="message_deleted_by_commissioner" if is_moderator and not is_owner else "message_deleted_by_sender",
            metadata_json={"sender_user_id": message.sender_user_id},
        )
        db.commit()
        db.refresh(message)
    return _message_read(db, message)


def mark_thread_read(
    db: Session,
    *,
    request: Request,
    league_id: int,
    thread_id: int,
    current_user: User,
    payload: ChatReadStateUpdate,
) -> ChatReadReceipt:
    _require_thread_access(db, league_id=league_id, thread_id=thread_id, user_id=current_user.id)
    _enforce_chat_rate_limit(
        db,
        action="chat_mark_read",
        current_user=current_user,
        request=request,
        limit=settings.chat_read_rate_limit,
        window_minutes=settings.chat_read_rate_limit_window_minutes,
    )
    requested_message_id = payload.last_read_message_id
    if requested_message_id is None:
        latest = (
            db.query(ChatMessage.id)
            .filter(ChatMessage.thread_id == thread_id, ChatMessage.deleted_at.is_(None))
            .order_by(ChatMessage.id.desc())
            .first()
        )
        requested_message_id = latest[0] if latest else None
    elif not (
        db.query(ChatMessage.id)
        .filter(ChatMessage.id == requested_message_id, ChatMessage.thread_id == thread_id)
        .first()
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="read message must belong to this thread")

    state = (
        db.query(ChatReadState)
        .filter(ChatReadState.thread_id == thread_id, ChatReadState.user_id == current_user.id)
        .one_or_none()
    )
    if not state:
        state = ChatReadState(
            thread_id=thread_id,
            user_id=current_user.id,
            last_read_message_id=requested_message_id,
            last_read_at=utcnow(),
        )
    elif requested_message_id is None or (
        state.last_read_message_id is None or requested_message_id > state.last_read_message_id
    ):
        state.last_read_message_id = requested_message_id
        state.last_read_at = utcnow()
    elif requested_message_id < state.last_read_message_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="read cursor cannot move backward")
    db.add(state)
    db.commit()
    unread_count = _thread_unread_counts(db, thread_ids=[thread_id], user_id=current_user.id).get(thread_id, 0)
    summary = list_unread_summary(db, current_user=current_user)
    return ChatReadReceipt(
        thread_id=thread_id,
        league_id=league_id,
        unread_count=unread_count,
        total_unread=summary.total_unread,
    )


def list_unread_summary(db: Session, *, current_user: User) -> ChatUnreadSummary:
    memberships = db.query(LeagueMember.league_id).filter(LeagueMember.user_id == current_user.id).all()
    league_ids = [row[0] for row in memberships]
    if not league_ids:
        return ChatUnreadSummary(total_unread=0, leagues=[])
    threads = (
        db.query(ChatThread)
        .filter(ChatThread.league_id.in_(league_ids))
        .filter(
            or_(
                ChatThread.thread_type == "league",
                and_(
                    ChatThread.thread_type == "direct",
                    or_(
                        ChatThread.direct_user_low_id == current_user.id,
                        ChatThread.direct_user_high_id == current_user.id,
                    ),
                ),
            )
        )
        .all()
    )
    unread_counts = _thread_unread_counts(db, thread_ids=[thread.id for thread in threads], user_id=current_user.id)
    by_league: dict[int, int] = {}
    for thread in threads:
        count = unread_counts.get(thread.id, 0)
        if count:
            by_league[thread.league_id] = by_league.get(thread.league_id, 0) + count
    leagues = [
        ChatUnreadLeagueRead(league_id=league_id, unread=count)
        for league_id, count in sorted(by_league.items())
    ]
    return ChatUnreadSummary(total_unread=sum(item.unread for item in leagues), leagues=leagues)


def create_system_chat_message(
    db: Session,
    *,
    league_id: int,
    body: str,
    message_type: str = "system",
    metadata_json: dict | None = None,
    event_key: str | None = None,
) -> ChatMessage:
    if message_type not in SYSTEM_MESSAGE_TYPES:
        raise ValueError(f"unsupported chat system message type: {message_type}")
    if event_key:
        existing = db.query(ChatMessage).filter(ChatMessage.event_key == event_key).one_or_none()
        if existing:
            return existing
    thread = get_or_create_league_chat_thread(db, league_id)
    try:
        with db.begin_nested():
            message = ChatMessage(
                thread_id=thread.id,
                league_id=league_id,
                message_type=message_type,
                body=body,
                metadata_json=metadata_json or {},
                event_key=event_key,
            )
            thread.updated_at = utcnow()
            db.add_all((message, thread))
            db.flush()
    except IntegrityError:
        if event_key:
            existing = db.query(ChatMessage).filter(ChatMessage.event_key == event_key).one_or_none()
            if existing:
                return existing
        raise
    return message


def _trade_asset_metadata(item: TradeOfferItem) -> dict:
    """Serialize a trade asset without exposing mutable roster records."""
    player = item.player
    if player is None:
        return {
            "player_id": item.player_id,
            "name": "Unknown player",
            "position": None,
            "school": None,
        }
    return {
        "player_id": player.id,
        "name": player.name,
        "position": player.position,
        "school": player.school,
    }


def _trade_message_metadata(
    db: Session,
    offer: TradeOffer,
    *,
    finalized_at: datetime,
    process_after: datetime | None,
) -> dict:
    proposing = db.get(Team, offer.proposing_team_id)
    receiving = db.get(Team, offer.receiving_team_id)
    if proposing is None or receiving is None:
        raise ValueError("trade teams must exist before a finalized chat message can be created")

    return {
        "event_key": f"trade:{offer.id}:finalized",
        "trade_id": offer.id,
        "proposing_team": {"id": proposing.id, "name": proposing.name},
        "receiving_team": {"id": receiving.id, "name": receiving.name},
        "proposing_team_sends": [
            _trade_asset_metadata(item) for item in offer.items if item.team_id == proposing.id
        ],
        "receiving_team_sends": [
            _trade_asset_metadata(item) for item in offer.items if item.team_id == receiving.id
        ],
        "finalized_at": finalized_at.isoformat(),
        "players_process_at": process_after.isoformat() if process_after else None,
        "processing_status": "processed" if offer.processed_at else "pending_transfer",
        "processed_at": offer.processed_at.isoformat() if offer.processed_at else None,
    }


def create_trade_finalized_chat_message(
    db: Session,
    offer: TradeOffer,
    finalized_at: datetime,
    process_after: datetime | None,
) -> ChatMessage:
    """Atomically persist the one binding announcement for a finalized trade."""
    metadata_json = _trade_message_metadata(
        db,
        offer,
        finalized_at=finalized_at,
        process_after=process_after,
    )
    proposing_name = metadata_json["proposing_team"]["name"]
    receiving_name = metadata_json["receiving_team"]["name"]
    message = create_system_chat_message(
        db,
        league_id=offer.league_id,
        message_type="trade_finalized",
        body=f"{proposing_name} and {receiving_name} finalized a trade.",
        event_key=metadata_json["event_key"],
        metadata_json=metadata_json,
    )
    _record_chat_audit_event(
        db,
        league_id=offer.league_id,
        thread_id=message.thread_id,
        message_id=message.id,
        action="system_trade_message_generated",
        metadata_json={"trade_id": offer.id, "message_type": "trade_finalized"},
        event_key=f"trade:{offer.id}:finalized:chat-audit",
    )
    return message


def mark_trade_finalized_chat_message_processed(db: Session, offer: TradeOffer) -> ChatMessage | None:
    """Update the binding trade card after a delayed player transfer without a new event."""
    message = (
        db.query(ChatMessage)
        .filter(ChatMessage.event_key == f"trade:{offer.id}:finalized")
        .one_or_none()
    )
    if message is None:
        return None

    metadata_json = dict(message.metadata_json or {})
    metadata_json["processing_status"] = "processed"
    metadata_json["processed_at"] = offer.processed_at.isoformat() if offer.processed_at else utcnow().isoformat()
    message.metadata_json = metadata_json
    message.updated_at = utcnow()
    db.add(message)
    return message
