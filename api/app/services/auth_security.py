from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import generate_token, hash_token
from collegefootballfantasy_api.app.models.auth_action_token import AuthActionToken
from collegefootballfantasy_api.app.models.auth_rate_limit_event import AuthRateLimitEvent
from collegefootballfantasy_api.app.models.refresh_session import RefreshSession
from collegefootballfantasy_api.app.models.user import User

EMAIL_VERIFICATION_TOKEN = "email_verification"
PASSWORD_RESET_TOKEN = "password_reset"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def request_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def _safe_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hash_token(value.strip().lower())


def enforce_auth_rate_limit(
    db: Session,
    *,
    action: str,
    identifier: str | None,
    request: Request,
    limit: int,
    window_minutes: int | None = None,
) -> None:
    now = utcnow()
    window_start = now - timedelta(minutes=window_minutes or settings.auth_rate_limit_window_minutes)
    identifier_hash = _safe_hash(identifier)
    ip_hash = _safe_hash(request_ip(request))

    filters = []
    if identifier_hash:
        filters.append(AuthRateLimitEvent.identifier_hash == identifier_hash)
    if ip_hash:
        filters.append(AuthRateLimitEvent.ip_hash == ip_hash)

    if filters:
        count = (
            db.query(AuthRateLimitEvent)
            .filter(AuthRateLimitEvent.action == action)
            .filter(AuthRateLimitEvent.created_at >= window_start)
            .filter(or_(*filters))
            .count()
        )
        if count >= limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many requests")

    db.add(
        AuthRateLimitEvent(
            action=action,
            identifier_hash=identifier_hash,
            ip_hash=ip_hash,
            created_at=now,
        )
    )
    db.flush()


def create_auth_action_token(
    db: Session,
    *,
    user: User,
    token_type: str,
    ttl: timedelta,
    request: Request,
) -> str:
    now = utcnow()
    (
        db.query(AuthActionToken)
        .filter(
            AuthActionToken.user_id == user.id,
            AuthActionToken.token_type == token_type,
            AuthActionToken.consumed_at.is_(None),
        )
        .update({"consumed_at": now}, synchronize_session=False)
    )
    raw_token = generate_token(48)
    db.add(
        AuthActionToken(
            user_id=user.id,
            token_type=token_type,
            token_hash=hash_token(raw_token),
            email=user.email,
            expires_at=now + ttl,
            request_ip_hash=_safe_hash(request_ip(request)),
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.flush()
    return raw_token


def consume_auth_action_token(db: Session, *, token_type: str, token: str) -> AuthActionToken:
    now = utcnow()
    token_row = (
        db.query(AuthActionToken)
        .filter(AuthActionToken.token_type == token_type, AuthActionToken.token_hash == hash_token(token))
        .first()
    )
    if (
        not token_row
        or token_row.consumed_at is not None
        or ensure_aware(token_row.expires_at) is None
        or ensure_aware(token_row.expires_at) <= now
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token")
    token_row.consumed_at = now
    db.add(token_row)
    db.flush()
    return token_row


def is_account_locked(user: User) -> bool:
    locked_until = ensure_aware(user.locked_until)
    return locked_until is not None and locked_until > utcnow()


def register_failed_login(db: Session, user: User) -> None:
    now = utcnow()
    last_failed = ensure_aware(user.last_failed_login_at)
    if last_failed is None or last_failed < now - timedelta(minutes=settings.auth_failed_login_window_minutes):
        user.failed_login_attempts = 0
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    user.last_failed_login_at = now
    if user.failed_login_attempts >= settings.auth_failed_login_limit:
        user.locked_until = now + timedelta(minutes=settings.auth_lockout_minutes)
    db.add(user)
    db.flush()


def reset_failed_login_state(user: User) -> None:
    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None


def revoke_user_sessions(
    db: Session,
    *,
    user_id: int,
    except_session_id: int | None = None,
    now: datetime | None = None,
) -> int:
    revoked_at = now or utcnow()
    query = db.query(RefreshSession).filter(
        RefreshSession.user_id == user_id,
        RefreshSession.revoked_at.is_(None),
    )
    if except_session_id is not None:
        query = query.filter(RefreshSession.id != except_session_id)
    return query.update({"revoked_at": revoked_at, "last_used_at": revoked_at}, synchronize_session=False)
