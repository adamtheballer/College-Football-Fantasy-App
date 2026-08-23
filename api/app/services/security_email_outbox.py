"""Delivery of durable, high-priority security email through the lifecycle worker."""

from __future__ import annotations

from datetime import timedelta
from html import escape

from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.auth_action_token import AuthActionToken
from collegefootballfantasy_api.app.models.security_audit_event import SecurityAuditEvent
from collegefootballfantasy_api.app.models.security_email_outbox import SecurityEmailOutbox
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.auth_security import utcnow
from collegefootballfantasy_api.app.services.email_service import EmailPayload, get_email_service
from collegefootballfantasy_api.app.services.password_reset import token_for_delivery


def _canonical_public_url() -> str:
    value = settings.public_web_url or settings.ui_base_url
    return value.rstrip("/")


def _message(row: SecurityEmailOutbox, user: User, token_row: AuthActionToken | None) -> EmailPayload:
    if row.message_type == "password_reset":
        if token_row is None:
            raise RuntimeError("reset email outbox row has no token")
        link = f"{_canonical_public_url()}/reset-password?token={token_for_delivery(token_row)}"
        text = (
            "RESET YOUR PASSWORD\n\n"
            "A request was made to reset your College Football Fantasy password.\n\n"
            f"Reset Password: {link}\n\n"
            "This link expires in 30 minutes and can only be used once. If you did not request this, ignore this email; your password will continue to work."
        )
        html = (
            "<h1>RESET YOUR PASSWORD</h1><p>A request was made to reset your College Football Fantasy password.</p>"
            f'<p><a href="{escape(link, quote=True)}">RESET PASSWORD</a></p>'
            "<p>This link expires in 30 minutes and can only be used once.</p>"
            "<p>If you did not request this, ignore this email. Your current password will continue to work.</p>"
        )
        subject = "Reset your College Football Fantasy password"
    else:
        text = (
            "YOUR PASSWORD WAS CHANGED\n\n"
            "Your College Football Fantasy password was changed. If you did not make this change, contact support immediately."
        )
        html = "<h1>YOUR PASSWORD WAS CHANGED</h1><p>If you did not make this change, contact support immediately.</p>"
        subject = "Your College Football Fantasy password was changed"
    return EmailPayload(
        to_email=user.email,
        subject=subject,
        body=text,
        html_body=html,
        message_id=f"<security-email-{row.idempotency_key}@collegefantasyfootball.org>",
    )


def _audit(db: Session, row: SecurityEmailOutbox, event_type: str, outcome: str) -> None:
    db.add(SecurityAuditEvent(
        user_id=row.user_id,
        event_type=event_type,
        outcome=outcome,
        provider_message_id=row.provider_message_id,
        created_at=utcnow(),
    ))


def process_security_email_outbox_once(db: Session, limit: int = 20) -> dict[str, int]:
    """Claim rows before sending; a lease prevents duplicate concurrent workers."""
    if not settings.email_enabled:
        return {"delivered": 0, "failed": 0, "deferred": 0}
    now = utcnow()
    rows = (
        db.query(SecurityEmailOutbox)
        .filter(
            or_(
                (SecurityEmailOutbox.status == "pending") & (SecurityEmailOutbox.next_attempt_at.is_(None)),
                (SecurityEmailOutbox.status == "pending") & (SecurityEmailOutbox.next_attempt_at <= now),
                (SecurityEmailOutbox.status == "sending") & (SecurityEmailOutbox.lease_expires_at <= now),
            )
        )
        .order_by(SecurityEmailOutbox.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
        .all()
    )
    for row in rows:
        row.status = "sending"
        row.lease_expires_at = now + timedelta(seconds=120)
    db.commit()

    result = {"delivered": 0, "failed": 0, "deferred": 0}
    for row_id in [row.id for row in rows]:
        row = db.get(SecurityEmailOutbox, row_id)
        if row is None:
            continue
        try:
            user = db.get(User, row.user_id)
            token_row = db.get(AuthActionToken, row.auth_action_token_id) if row.auth_action_token_id else None
            if user is None:
                raise RuntimeError("security email recipient no longer exists")
            get_email_service().send(_message(row, user, token_row))
            row.status = "delivered"
            row.delivered_at = utcnow()
            row.lease_expires_at = None
            row.provider_message_id = row.idempotency_key
            _audit(db, row, "PASSWORD_RESET_EMAIL_DELIVERED" if row.message_type == "password_reset" else "PASSWORD_CHANGED_EMAIL_DELIVERED", "delivered")
            db.commit()
            result["delivered"] += 1
        except Exception as exc:  # provider errors are safe to retry; no token is logged
            db.rollback()
            row = db.get(SecurityEmailOutbox, row_id)
            if row is None:
                continue
            row.attempt_count += 1
            row.lease_expires_at = None
            row.last_error = type(exc).__name__[:500]
            if row.attempt_count >= settings.password_reset_email_max_attempts:
                row.status = "dead"
                result["failed"] += 1
            else:
                row.status = "pending"
                row.next_attempt_at = utcnow() + timedelta(seconds=min(3600, 2 ** row.attempt_count * 30))
                result["deferred"] += 1
            _audit(db, row, "PASSWORD_RESET_EMAIL_FAILED", "failed")
            db.commit()
    return result
