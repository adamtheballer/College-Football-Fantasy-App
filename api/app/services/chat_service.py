from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_message import (
    LeagueMessage,
    LeagueMessageRead as LeagueMessageReadCursor,
    LeagueMessageReport,
)
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
from collegefootballfantasy_api.app.services.audit_service import record_audit_event

SYSTEM_MESSAGE_TYPES = {"system", "trade", "waiver", "draft", "scoring", "commissioner"}
RATE_LIMIT_WINDOW_SECONDS = 30
RATE_LIMIT_MAX_MESSAGES = 8
SPAM_BLOCKLIST = {"http://", "https://bit.ly", "free money", "crypto pump"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _membership(db: Session, league_id: int, user_id: int) -> LeagueMember:
    row = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="league membership required")
    return row


def _is_commissioner(league: League, membership: LeagueMember, user: User) -> bool:
    return league.commissioner_user_id == user.id or membership.role == "commissioner"


def _message_or_404(db: Session, *, league_id: int, message_id: int) -> LeagueMessage:
    row = db.get(LeagueMessage, message_id)
    if not row or row.league_id != league_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="message not found")
    return row


def _visible_body(row: LeagueMessage) -> str:
    if row.deleted_at is not None:
        return "[deleted]"
    return row.body


def _serialize_message(row: LeagueMessage, *, current_user: User, is_commissioner: bool) -> LeagueMessageRead:
    can_edit = row.deleted_at is None and row.user_id == current_user.id and row.message_type == "user"
    can_delete = row.deleted_at is None and (row.user_id == current_user.id or is_commissioner)
    return LeagueMessageRead(
        id=row.id,
        league_id=row.league_id,
        user_id=row.user_id,
        body=_visible_body(row),
        message_type=row.message_type,
        parent_message_id=row.parent_message_id,
        deleted_at=row.deleted_at,
        edited_at=row.edited_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        can_edit=can_edit,
        can_delete=can_delete,
    )


def _unread_count(db: Session, *, league_id: int, user_id: int) -> int:
    cursor = (
        db.query(LeagueMessageReadCursor)
        .filter(LeagueMessageReadCursor.league_id == league_id, LeagueMessageReadCursor.user_id == user_id)
        .first()
    )
    query = db.query(func.count(LeagueMessage.id)).filter(
        LeagueMessage.league_id == league_id,
        LeagueMessage.deleted_at.is_(None),
        LeagueMessage.user_id != user_id,
    )
    if cursor and cursor.last_read_message_id is not None:
        query = query.filter(LeagueMessage.id > cursor.last_read_message_id)
    return int(query.scalar() or 0)


def _assert_not_spam(body: str) -> None:
    lowered = body.lower()
    if any(blocked in lowered for blocked in SPAM_BLOCKLIST):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message failed spam guard")


def _assert_rate_limit(db: Session, *, league_id: int, user_id: int) -> None:
    since = _utc_now() - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    recent_count = (
        db.query(func.count(LeagueMessage.id))
        .filter(
            LeagueMessage.league_id == league_id,
            LeagueMessage.user_id == user_id,
            LeagueMessage.message_type == "user",
            LeagueMessage.created_at >= since,
        )
        .scalar()
    )
    if int(recent_count or 0) >= RATE_LIMIT_MAX_MESSAGES:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="chat rate limit exceeded")


def list_messages(
    db: Session,
    *,
    league: League,
    current_user: User,
    limit: int = 50,
    before_id: int | None = None,
    after_id: int | None = None,
) -> LeagueMessageList:
    membership = _membership(db, league.id, current_user.id)
    is_commissioner = _is_commissioner(league, membership, current_user)
    capped_limit = max(1, min(limit, 100))
    query = db.query(LeagueMessage).filter(LeagueMessage.league_id == league.id)
    if before_id is not None:
        query = query.filter(LeagueMessage.id < before_id)
    if after_id is not None:
        query = query.filter(LeagueMessage.id > after_id)
    total = int(db.query(func.count(LeagueMessage.id)).filter(LeagueMessage.league_id == league.id).scalar() or 0)
    rows = query.order_by(LeagueMessage.id.desc()).limit(capped_limit).all()
    rows.reverse()
    return LeagueMessageList(
        data=[_serialize_message(row, current_user=current_user, is_commissioner=is_commissioner) for row in rows],
        total=total,
        limit=capped_limit,
        before_id=before_id,
        after_id=after_id,
        unread_count=_unread_count(db, league_id=league.id, user_id=current_user.id),
    )


def create_message(db: Session, *, league: League, payload: LeagueMessageCreate, current_user: User) -> LeagueMessageRead:
    membership = _membership(db, league.id, current_user.id)
    is_commissioner = _is_commissioner(league, membership, current_user)
    if payload.message_type in SYSTEM_MESSAGE_TYPES and not is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner message type required")
    if payload.parent_message_id is not None:
        parent = _message_or_404(db, league_id=league.id, message_id=payload.parent_message_id)
        if parent.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot reply to deleted message")
    if payload.message_type == "user":
        _assert_rate_limit(db, league_id=league.id, user_id=current_user.id)
    _assert_not_spam(payload.body)
    row = LeagueMessage(
        league_id=league.id,
        user_id=current_user.id,
        body=payload.body,
        message_type=payload.message_type,
        parent_message_id=payload.parent_message_id,
    )
    db.add(row)
    db.flush()
    record_audit_event(
        db,
        action="league.chat.message.create",
        entity_type="league_message",
        entity_id=row.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        after={"message_type": row.message_type, "parent_message_id": row.parent_message_id},
    )
    db.commit()
    db.refresh(row)
    return _serialize_message(row, current_user=current_user, is_commissioner=is_commissioner)


def update_message(
    db: Session,
    *,
    league: League,
    message_id: int,
    payload: LeagueMessageUpdate,
    current_user: User,
) -> LeagueMessageRead:
    membership = _membership(db, league.id, current_user.id)
    row = _message_or_404(db, league_id=league.id, message_id=message_id)
    if row.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="message is deleted")
    if row.user_id != current_user.id or row.message_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="message author required")
    _assert_not_spam(payload.body)
    before = {"body": row.body}
    row.body = payload.body
    row.edited_at = _utc_now()
    db.add(row)
    record_audit_event(
        db,
        action="league.chat.message.edit",
        entity_type="league_message",
        entity_id=row.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before=before,
        after={"body": row.body},
    )
    db.commit()
    db.refresh(row)
    return _serialize_message(row, current_user=current_user, is_commissioner=_is_commissioner(league, membership, current_user))


def delete_message(db: Session, *, league: League, message_id: int, current_user: User) -> LeagueMessageRead:
    membership = _membership(db, league.id, current_user.id)
    is_commissioner = _is_commissioner(league, membership, current_user)
    row = _message_or_404(db, league_id=league.id, message_id=message_id)
    if row.deleted_at is not None:
        return _serialize_message(row, current_user=current_user, is_commissioner=is_commissioner)
    if row.user_id != current_user.id and not is_commissioner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="message author or commissioner required")
    row.deleted_at = _utc_now()
    db.add(row)
    record_audit_event(
        db,
        action="league.chat.message.delete",
        entity_type="league_message",
        entity_id=row.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before={"body": row.body},
        after={"deleted_at": row.deleted_at.isoformat()},
    )
    db.commit()
    db.refresh(row)
    return _serialize_message(row, current_user=current_user, is_commissioner=is_commissioner)


def report_message(
    db: Session,
    *,
    league: League,
    message_id: int,
    payload: LeagueMessageReportCreate,
    current_user: User,
) -> LeagueMessageReportRead:
    _membership(db, league.id, current_user.id)
    row = _message_or_404(db, league_id=league.id, message_id=message_id)
    if row.user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot report your own message")
    report = LeagueMessageReport(
        message_id=row.id,
        reporter_user_id=current_user.id,
        reason=payload.reason,
        status="open",
    )
    db.add(report)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="message already reported") from exc
    record_audit_event(
        db,
        action="league.chat.message.report",
        entity_type="league_message_report",
        entity_id=report.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        after={"message_id": row.id, "reason": payload.reason},
    )
    db.commit()
    db.refresh(report)
    return LeagueMessageReportRead.model_validate(report)


def mark_chat_read(
    db: Session,
    *,
    league: League,
    payload: LeagueChatReadUpdate,
    current_user: User,
) -> LeagueChatReadState:
    _membership(db, league.id, current_user.id)
    last_message_id = payload.last_read_message_id
    if last_message_id is None:
        last_message_id = (
            db.query(func.max(LeagueMessage.id))
            .filter(LeagueMessage.league_id == league.id)
            .scalar()
        )
    if last_message_id is not None:
        _message_or_404(db, league_id=league.id, message_id=int(last_message_id))

    cursor = (
        db.query(LeagueMessageReadCursor)
        .filter(LeagueMessageReadCursor.league_id == league.id, LeagueMessageReadCursor.user_id == current_user.id)
        .first()
    )
    if not cursor:
        cursor = LeagueMessageReadCursor(league_id=league.id, user_id=current_user.id)
    cursor.last_read_message_id = int(last_message_id) if last_message_id is not None else None
    cursor.last_read_at = _utc_now()
    db.add(cursor)
    db.commit()
    db.refresh(cursor)
    return LeagueChatReadState(
        league_id=league.id,
        last_read_message_id=cursor.last_read_message_id,
        last_read_at=cursor.last_read_at,
        unread_count=_unread_count(db, league_id=league.id, user_id=current_user.id),
    )


def create_system_message(
    db: Session,
    *,
    league_id: int,
    user_id: int,
    body: str,
    message_type: str,
    parent_message_id: int | None = None,
) -> LeagueMessage:
    if message_type not in SYSTEM_MESSAGE_TYPES:
        raise ValueError("system chat messages must use a system message type")
    row = LeagueMessage(
        league_id=league_id,
        user_id=user_id,
        body=body.strip(),
        message_type=message_type,
        parent_message_id=parent_message_id,
    )
    db.add(row)
    db.flush()
    return row
