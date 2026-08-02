from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64DecodeError
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.auth_rate_limit_event import AuthRateLimitEvent
from collegefootballfantasy_api.app.models.beta_access import BetaAccessAuditEvent, BetaAccessCode
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.auth_security import ensure_aware, request_ip, utcnow

GENERIC_MISMATCH_MESSAGE = "The email and early-access code do not match, or the code is no longer available."
RATE_LIMIT_MESSAGE = "Too many attempts. Please try again later."
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_PATTERN = re.compile(r"^EARLY-[A-Z0-9]{6}$")

AUDIT_IMPORTED = "BETA_CODE_IMPORTED"
AUDIT_IMPORT_REJECTED = "BETA_CODE_IMPORT_REJECTED"
AUDIT_HMAC_REKEYED = "BETA_CODE_HMAC_REKEYED"
AUDIT_VALIDATION_SUCCEEDED = "BETA_CODE_VALIDATION_SUCCEEDED"
AUDIT_VALIDATION_FAILED = "BETA_CODE_VALIDATION_FAILED"
AUDIT_RESERVED = "BETA_CODE_RESERVED"
AUDIT_RESERVATION_EXPIRED = "BETA_CODE_RESERVATION_EXPIRED"
AUDIT_RESERVATION_RELEASED = "BETA_CODE_RESERVATION_RELEASED"
AUDIT_REDEEMED = "BETA_CODE_REDEEMED"
AUDIT_ACCESS_GRANTED = "BETA_ACCESS_GRANTED"
AUDIT_CONCURRENT_REDEMPTION_BLOCKED = "BETA_CONCURRENT_REDEMPTION_BLOCKED"


def normalize_beta_email(value: str) -> str:
    normalized = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("invalid email")
    return normalized


def normalize_beta_code(value: str) -> str:
    normalized = value.strip().upper()
    if not CODE_PATTERN.fullmatch(normalized):
        raise ValueError("invalid code")
    return normalized


def beta_access_hmac(value: str, *, purpose: str) -> str:
    payload = f"{purpose}:{value}".encode("utf-8")
    return hmac.new(settings.beta_access_code_hmac_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _b64_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64_decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _reservation_token(*, code_id: int, nonce: str, expires_at: datetime) -> str:
    payload = json.dumps(
        {"code_id": code_id, "nonce": nonce, "exp": int(expires_at.timestamp())}, separators=(",", ":")
    ).encode("utf-8")
    encoded = _b64_encode(payload)
    signature = hmac.new(
        settings.beta_access_reservation_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256
    ).digest()
    return f"{encoded}.{_b64_encode(signature)}"


def _parse_reservation_token(token: str) -> tuple[int, str, datetime]:
    try:
        encoded, provided = token.split(".", 1)
        expected = hmac.new(
            settings.beta_access_reservation_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_b64_decode(provided), expected):
            raise ValueError("invalid signature")
        payload = json.loads(_b64_decode(encoded).decode("utf-8"))
        code_id = int(payload["code_id"])
        nonce = str(payload["nonce"])
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=utcnow().tzinfo)
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError, Base64DecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_MISMATCH_MESSAGE) from exc
    if not nonce or expires_at <= utcnow():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_MISMATCH_MESSAGE)
    return code_id, nonce, expires_at


def _audit(
    db: Session,
    *,
    action: str,
    code: BetaAccessCode | None = None,
    email: str | None = None,
    supplied_code: str | None = None,
    request: Request | None = None,
) -> None:
    db.add(
        BetaAccessAuditEvent(
            beta_access_code_id=code.id if code else None,
            action=action,
            email_hmac=beta_access_hmac(email, purpose="email") if email else None,
            code_hmac=beta_access_hmac(supplied_code, purpose="code") if supplied_code else None,
            ip_hmac=beta_access_hmac(request_ip(request), purpose="ip") if request and request_ip(request) else None,
            created_at=utcnow(),
        )
    )


def _record_validation_failure(
    db: Session,
    *,
    email: str | None,
    supplied_code: str | None,
    request: Request,
    code: BetaAccessCode | None = None,
) -> None:
    _audit(
        db,
        action=AUDIT_VALIDATION_FAILED,
        code=code,
        email=email,
        supplied_code=supplied_code,
        request=request,
    )
    # Reuse the existing durable limiter table, but key the identifiers with a
    # beta-specific HMAC so neither raw values nor unsalted hashes are stored.
    ip_value = request_ip(request)
    for action, identifier in (
        ("beta_access_failed_email", email),
        ("beta_access_failed_code", supplied_code),
        ("beta_access_failed_ip", ip_value),
    ):
        if identifier:
            db.add(
                AuthRateLimitEvent(
                    action=action,
                    identifier_hash=beta_access_hmac(identifier, purpose=action),
                    ip_hash=beta_access_hmac(ip_value, purpose="ip") if ip_value else None,
                    created_at=utcnow(),
                )
            )


def _limit_reached(db: Session, *, action: str, fingerprint: str | None, limit: int) -> bool:
    if not fingerprint:
        return False
    window_start = utcnow() - timedelta(minutes=settings.beta_access_rate_limit_window_minutes)
    return (
        db.query(AuthRateLimitEvent)
        .filter(
            AuthRateLimitEvent.action == action,
            AuthRateLimitEvent.identifier_hash == fingerprint,
            AuthRateLimitEvent.created_at >= window_start,
        )
        .count()
        >= limit
    )


def _enforce_validation_rate_limits(db: Session, *, email: str | None, supplied_code: str | None, request: Request) -> None:
    ip_value = request_ip(request)
    checks = (
        ("beta_access_failed_email", beta_access_hmac(email, purpose="beta_access_failed_email") if email else None, settings.beta_access_failed_email_limit),
        ("beta_access_failed_code", beta_access_hmac(supplied_code, purpose="beta_access_failed_code") if supplied_code else None, settings.beta_access_failed_code_limit),
        ("beta_access_failed_ip", beta_access_hmac(ip_value, purpose="beta_access_failed_ip") if ip_value else None, settings.beta_access_failed_ip_limit),
    )
    if any(_limit_reached(db, action=action, fingerprint=fingerprint, limit=limit) for action, fingerprint, limit in checks):
        _audit(db, action="validation_rate_limited", email=email, supplied_code=supplied_code, request=request)
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_MESSAGE)


def _release_expired_reservation(code: BetaAccessCode, *, now: datetime) -> None:
    expires_at = ensure_aware(code.reservation_expires_at)
    if code.state == "RESERVED" and expires_at is not None and expires_at <= now:
        code.state = "AVAILABLE"
        code.reserved_at = None
        code.reservation_expires_at = None
        code.reservation_nonce_hmac = None


def validate_and_reserve_beta_access(
    db: Session, *, email_input: str, code_input: str, request: Request
) -> tuple[str, datetime, str]:
    normalized_email: str | None
    normalized_code: str | None
    try:
        normalized_email = normalize_beta_email(email_input)
    except ValueError:
        normalized_email = None
    try:
        normalized_code = normalize_beta_code(code_input)
    except ValueError:
        normalized_code = None

    _enforce_validation_rate_limits(db, email=normalized_email, supplied_code=normalized_code, request=request)
    if not normalized_email or not normalized_code:
        _record_validation_failure(db, email=normalized_email, supplied_code=normalized_code, request=request)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_MISMATCH_MESSAGE)

    code_hmac = beta_access_hmac(normalized_code, purpose="code")
    # The email is retained only for the verified account-creation handoff.
    # The code itself is never retained, queried, or emitted in raw form.
    code = (
        db.query(BetaAccessCode)
        .filter(BetaAccessCode.email == normalized_email, BetaAccessCode.code_hmac == code_hmac)
        .with_for_update()
        .one_or_none()
    )
    now = utcnow()
    if code:
        existing_expiry = ensure_aware(code.reservation_expires_at)
        was_expired = code.state == "RESERVED" and existing_expiry is not None and existing_expiry <= now
        _release_expired_reservation(code, now=now)
        if was_expired:
            _audit(db, action=AUDIT_RESERVATION_EXPIRED, code=code, email=normalized_email, request=request)

    if not code or code.manual_review or code.source_status != "READY_SENT" or code.state == "REDEEMED":
        _record_validation_failure(db, email=normalized_email, supplied_code=normalized_code, request=request, code=code)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_MISMATCH_MESSAGE)

    if code.state == "RESERVED":
        _record_validation_failure(db, email=normalized_email, supplied_code=normalized_code, request=request, code=code)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_MISMATCH_MESSAGE)

    nonce = secrets.token_urlsafe(32)
    # Reservation tokens encode an epoch second. Persist the same precision so
    # a valid token cannot fail a strict database/token expiry comparison just
    # because the database retained microseconds that were not signed.
    expires_at = (now + timedelta(minutes=settings.beta_access_reservation_ttl_minutes)).replace(microsecond=0)
    code.state = "RESERVED"
    code.reserved_at = now
    code.reservation_expires_at = expires_at
    code.reservation_nonce_hmac = beta_access_hmac(nonce, purpose="reservation_nonce")
    _audit(db, action=AUDIT_VALIDATION_SUCCEEDED, code=code, email=normalized_email, request=request)
    _audit(db, action=AUDIT_RESERVED, code=code, email=normalized_email, request=request)
    db.commit()
    return _reservation_token(code_id=code.id, nonce=nonce, expires_at=expires_at), expires_at, code.email


def consume_beta_access_reservation(db: Session, *, token: str) -> BetaAccessCode:
    code_id, nonce, token_expires_at = _parse_reservation_token(token)
    code = db.query(BetaAccessCode).filter(BetaAccessCode.id == code_id).with_for_update().one_or_none()
    expires_at = ensure_aware(code.reservation_expires_at) if code else None
    if (
        not code
        or code.manual_review
        or code.source_status != "READY_SENT"
        or code.state != "RESERVED"
        or expires_at is None
        or expires_at <= utcnow()
        or expires_at != token_expires_at
        or not code.reservation_nonce_hmac
        or not hmac.compare_digest(code.reservation_nonce_hmac, beta_access_hmac(nonce, purpose="reservation_nonce"))
    ):
        if code and code.state == "REDEEMED":
            _audit(db, action=AUDIT_CONCURRENT_REDEMPTION_BLOCKED, code=code)
            # This is outside the account-creation transaction: a prior
            # request already redeemed the code. Persist the security audit
            # event before returning the generic rejection.
            db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_MISMATCH_MESSAGE)
    return code


def release_beta_access_reservation(db: Session, *, code: BetaAccessCode, request: Request) -> None:
    """Make a valid-but-unredeemed code immediately available after a failed signup."""
    if code.state != "RESERVED":
        return
    code.state = "AVAILABLE"
    code.reserved_at = None
    code.reservation_expires_at = None
    code.reservation_nonce_hmac = None
    db.add(code)
    _audit(db, action=AUDIT_RESERVATION_RELEASED, code=code, email=code.email, request=request)


def redeem_beta_access(db: Session, *, code: BetaAccessCode, user: User, request: Request) -> None:
    now = utcnow()
    code.state = "REDEEMED"
    code.redeemed_at = now
    code.redeemed_user_id = user.id
    code.reserved_at = None
    code.reservation_expires_at = None
    code.reservation_nonce_hmac = None
    user.beta_access_granted_at = now
    db.add(code)
    db.add(user)
    _audit(
        db,
        action=AUDIT_REDEEMED,
        code=code,
        email=user.email,
        request=request,
    )
    _audit(db, action=AUDIT_ACCESS_GRANTED, code=code, email=user.email, request=request)
