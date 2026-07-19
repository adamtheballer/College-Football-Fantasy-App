from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.security import hash_password, verify_password
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.auth import validate_password_strength
from collegefootballfantasy_api.app.services.auth_security import reset_failed_login_state, revoke_user_sessions, utcnow


class PasswordChangeCredentialError(ValueError):
    """Raised when the supplied current password cannot be verified."""


class PasswordChangeValidationError(ValueError):
    """Raised when the requested replacement password is not allowed."""


def change_user_password(
    db: Session,
    *,
    user: User,
    current_password: str,
    new_password: str,
    confirm_new_password: str,
) -> int:
    """Atomically replace a verified user's password and revoke every session.

    This function deliberately does not commit. The route owns the surrounding
    request transaction so its rate-limit event and this security update share
    one commit. A failed update rolls back all password and session changes.
    """
    if not verify_password(current_password, user.password_hash):
        raise PasswordChangeCredentialError("current password did not verify")
    if new_password != confirm_new_password:
        raise PasswordChangeValidationError("new passwords do not match")
    try:
        validate_password_strength(new_password)
    except ValueError as exc:
        raise PasswordChangeValidationError(str(exc)) from exc
    if verify_password(new_password, user.password_hash):
        raise PasswordChangeValidationError("new password must differ from current password")

    now = utcnow()
    try:
        with db.begin_nested():
            user.password_hash = hash_password(new_password)
            user.password_changed_at = now
            user.auth_version += 1
            reset_failed_login_state(user)
            sessions_revoked = revoke_user_sessions(db, user_id=user.id, now=now)
            db.add(user)
            db.flush()
        return sessions_revoked
    except Exception:
        db.rollback()
        raise
