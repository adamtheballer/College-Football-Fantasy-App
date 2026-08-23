"""Single-use password-reset workflow and durable security-email queue."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import generate_token, hash_password, verify_password
from collegefootballfantasy_api.app.models.auth_action_token import AuthActionToken
from collegefootballfantasy_api.app.models.security_audit_event import SecurityAuditEvent
from collegefootballfantasy_api.app.models.security_email_outbox import SecurityEmailOutbox
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.auth import validate_password_strength
from collegefootballfantasy_api.app.services.auth_security import ensure_aware, request_ip, reset_failed_login_state, revoke_user_sessions, utcnow

PASSWORD_RESET_TOKEN = "password_reset"
GENERIC_RESET_MESSAGE = "If an account exists for that email, a password reset link has been sent."
INVALID_RESET_TOKEN_MESSAGE = "This reset link is invalid or expired."


def _hmac(value: str, purpose: str) -> str:
    return hmac.new(
        settings.password_reset_token_secret.encode("utf-8"),
        f"{purpose}:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _safe_hash(value: str | None, purpose: str) -> str | None:
    return _hmac(value.strip().lower(), purpose) if value else None


def _request_id() -> str:
    # 48 URL-safe characters contain well over the required 256 bits of entropy.
    return generate_token(48)


def _token_for_request(request_id: str) -> str:
    raw = hmac.new(
        settings.password_reset_token_secret.encode("utf-8"),
        f"password-reset-email-link:{request_id}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _token_digest(raw_token: str) -> str:
    return _hmac(raw_token, "password-reset-token-digest")


def token_for_delivery(token_row: AuthActionToken) -> str:
    if not token_row.request_id:
        raise RuntimeError("password reset token is missing its delivery request id")
    return _token_for_request(token_row.request_id)


def _record_event(db: Session, *, event_type: str, outcome: str, request: Request, user_id: int | None = None) -> None:
    db.add(
        SecurityAuditEvent(
            user_id=user_id,
            event_type=event_type,
            outcome=outcome,
            request_id=getattr(request.state, "request_id", None),
            ip_hash=_safe_hash(request_ip(request), "security-ip"),
            user_agent_hash=_safe_hash(request.headers.get("user-agent"), "security-user-agent"),
            created_at=utcnow(),
        )
    )


def _queue_email(db: Session, *, user_id: int, message_type: str, token_id: int | None = None) -> None:
    suffix = str(token_id) if token_id is not None else generate_token(32)
    db.add(
        SecurityEmailOutbox(
            user_id=user_id,
            auth_action_token_id=token_id,
            message_type=message_type,
            idempotency_key=f"{message_type}:{suffix}",
            status="pending",
        )
    )


def create_reset_request(db: Session, *, user: User, request: Request) -> AuthActionToken:
    """Create a reset request. The emailed token is never persisted."""
    now = utcnow()
    superseded_token_ids = [
        row_id
        for (row_id,) in db.query(AuthActionToken.id).filter(
            AuthActionToken.user_id == user.id,
            AuthActionToken.token_type == PASSWORD_RESET_TOKEN,
            AuthActionToken.consumed_at.is_(None),
            AuthActionToken.revoked_at.is_(None),
        ).all()
    ]
    db.query(AuthActionToken).filter(
        AuthActionToken.user_id == user.id,
        AuthActionToken.token_type == PASSWORD_RESET_TOKEN,
        AuthActionToken.consumed_at.is_(None),
        AuthActionToken.revoked_at.is_(None),
    ).update({"revoked_at": now, "revoke_reason": "superseded"}, synchronize_session=False)
    if superseded_token_ids:
        # A delayed worker must not send an already-invalidated reset link.
        db.query(SecurityEmailOutbox).filter(
            SecurityEmailOutbox.auth_action_token_id.in_(superseded_token_ids),
            SecurityEmailOutbox.status.in_(("pending", "sending")),
        ).update({"status": "cancelled", "lease_expires_at": None}, synchronize_session=False)

    request_id = _request_id()
    raw_token = _token_for_request(request_id)
    token_row = AuthActionToken(
        user_id=user.id,
        token_type=PASSWORD_RESET_TOKEN,
        token_hash=_token_digest(raw_token),
        email=user.email,
        request_id=request_id,
        expires_at=now + timedelta(minutes=settings.auth_password_reset_ttl_minutes),
        request_ip_hash=_safe_hash(request_ip(request), "security-ip"),
        user_agent=_safe_hash(request.headers.get("user-agent"), "security-user-agent"),
    )
    db.add(token_row)
    db.flush()
    _queue_email(db, user_id=user.id, message_type="password_reset", token_id=token_row.id)
    _record_event(db, event_type="PASSWORD_RESET_REQUESTED", outcome="queued", request=request, user_id=user.id)
    return token_row


def validate_reset_token(db: Session, token: str) -> AuthActionToken | None:
    token_row = (
        db.query(AuthActionToken)
        .filter(AuthActionToken.token_type == PASSWORD_RESET_TOKEN, AuthActionToken.token_hash == _token_digest(token))
        .one_or_none()
    )
    if token_row is None or token_row.consumed_at or token_row.revoked_at:
        return None
    if ensure_aware(token_row.expires_at) is None or ensure_aware(token_row.expires_at) <= utcnow():
        return None
    user = db.get(User, token_row.user_id)
    return token_row if user and user.is_active else None


def complete_reset(
    db: Session,
    *,
    token: str,
    new_password: str,
    confirm_password: str,
    request: Request,
) -> None:
    """Atomically replace the password and invalidate every credential."""
    if new_password != confirm_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="new passwords do not match")
    try:
        validate_password_strength(new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    now = utcnow()
    try:
        with db.begin_nested():
            token_row = (
                db.query(AuthActionToken)
                .filter(AuthActionToken.token_type == PASSWORD_RESET_TOKEN, AuthActionToken.token_hash == _token_digest(token))
                .with_for_update()
                .one_or_none()
            )
            if token_row is None or token_row.consumed_at or token_row.revoked_at or ensure_aware(token_row.expires_at) <= now:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_TOKEN_MESSAGE)
            user = db.query(User).filter(User.id == token_row.user_id).with_for_update().one_or_none()
            if user is None or not user.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_TOKEN_MESSAGE)
            if verify_password(new_password, user.password_hash):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="new password must differ from current password")

            user.password_hash = hash_password(new_password)
            user.password_changed_at = now
            user.auth_version += 1
            reset_failed_login_state(user)
            revoke_user_sessions(db, user_id=user.id, now=now)
            db.query(AuthActionToken).filter(
                AuthActionToken.user_id == user.id,
                AuthActionToken.token_type == PASSWORD_RESET_TOKEN,
                AuthActionToken.id != token_row.id,
                AuthActionToken.consumed_at.is_(None),
                AuthActionToken.revoked_at.is_(None),
            ).update({"revoked_at": now, "revoke_reason": "password_reset_completed"}, synchronize_session=False)
            token_row.consumed_at = now
            token_row.completed_ip_hash = _safe_hash(request_ip(request), "security-ip")
            token_row.completed_user_agent_hash = _safe_hash(request.headers.get("user-agent"), "security-user-agent")
            db.add(user)
            db.add(token_row)
            _queue_email(db, user_id=user.id, message_type="password_changed")
            _record_event(db, event_type="PASSWORD_RESET_COMPLETED", outcome="success", request=request, user_id=user.id)
            db.flush()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


def record_invalid_attempt(db: Session, *, request: Request) -> None:
    _record_event(db, event_type="PASSWORD_RESET_INVALID_ATTEMPT", outcome="invalid", request=request)
