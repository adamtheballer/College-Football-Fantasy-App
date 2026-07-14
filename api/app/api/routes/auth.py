from __future__ import annotations

import re
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import (
    create_access_token,
    generate_refresh_token,
    generate_token,
    hash_password,
    hash_token,
    needs_password_rehash,
    verify_password,
)
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.refresh_session import RefreshSession
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.auth import (
    AuthMessageResponse,
    AuthResponse,
    LogoutResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshResponse,
    ResendVerificationRequest,
    SessionRead,
    SessionsResponse,
    UserCreate,
    UserLogin,
    UserRead,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from collegefootballfantasy_api.app.services.auth_security import (
    EMAIL_VERIFICATION_TOKEN,
    PASSWORD_RESET_TOKEN,
    consume_auth_action_token,
    create_auth_action_token,
    enforce_auth_rate_limit,
    ensure_aware,
    is_account_locked,
    register_failed_login,
    request_ip,
    reset_failed_login_state,
    revoke_user_sessions,
    utcnow,
)
from collegefootballfantasy_api.app.services.email_service import get_email_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _normalize_username(value: str | None, *, fallback: str) -> str:
    raw_value = value or fallback
    normalized = re.sub(r"[^a-z0-9_]+", "-", raw_value.strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-_")
    if len(normalized) < 3:
        normalized = f"user-{normalized or 'manager'}"
    return normalized[:80]


def _unique_username(db: Session, desired: str) -> str:
    candidate = desired[:80]
    if not db.query(User).filter(User.username == candidate).first():
        return candidate
    suffix = 2
    while True:
        suffix_text = f"-{suffix}"
        candidate = f"{desired[: 80 - len(suffix_text)]}{suffix_text}"
        if not db.query(User).filter(User.username == candidate).first():
            return candidate
        suffix += 1


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path="/",
        domain=settings.refresh_cookie_domain,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path="/",
        domain=settings.refresh_cookie_domain,
    )


def _create_refresh_session(
    db: Session,
    *,
    user_id: int,
    request: Request,
    rotated_from_session_id: int | None = None,
) -> str:
    refresh_token = generate_refresh_token()
    now = utcnow()
    db.add(
        RefreshSession(
            user_id=user_id,
            token_hash=hash_token(refresh_token),
            issued_at=now,
            expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
            rotated_from_session_id=rotated_from_session_id,
            user_agent=request.headers.get("user-agent"),
            ip_address=request_ip(request),
        )
    )
    db.flush()
    return refresh_token


def _current_refresh_session(db: Session, request: Request) -> RefreshSession | None:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        return None
    return db.query(RefreshSession).filter(RefreshSession.token_hash == hash_token(refresh_token)).first()


def _send_verification_email(db: Session, *, user: User, request: Request) -> None:
    token = create_auth_action_token(
        db,
        user=user,
        token_type=EMAIL_VERIFICATION_TOKEN,
        ttl=timedelta(hours=settings.auth_email_verification_ttl_hours),
        request=request,
    )
    get_email_service().send_email_verification(user.email, token)


def _send_password_reset_email(db: Session, *, user: User, request: Request) -> None:
    token = create_auth_action_token(
        db,
        user=user,
        token_type=PASSWORD_RESET_TOKEN,
        ttl=timedelta(minutes=settings.auth_password_reset_ttl_minutes),
        request=request,
    )
    get_email_service().send_password_reset(user.email, token)


def _log_login_failure(request: Request, *, email: str, reason: str) -> None:
    logger.info(
        "auth_login_failed",
        extra={
            "normalized_email": email,
            "failure_reason": reason,
            "request_ip": request_ip(request),
        },
    )


@router.get("/me", response_model=UserRead)
def current_user_profile(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, response: Response, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    enforce_auth_rate_limit(
        db,
        action="signup",
        identifier=payload.email,
        request=request,
        limit=settings.auth_signup_rate_limit,
    )
    existing = db.query(User).filter(func.lower(User.email) == payload.email).first()
    if existing:
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

    username = _normalize_username(payload.username, fallback=payload.email.split("@", 1)[0])
    if payload.username and db.query(User).filter(User.username == username).first():
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already registered")

    now = utcnow()
    user = User(
        first_name=payload.first_name,
        email=payload.email,
        username=_unique_username(db, username),
        password_hash=hash_password(payload.password),
        api_token=generate_token(32),
        last_login=now,
        password_changed_at=now,
    )
    db.add(user)
    db.flush()
    _send_verification_email(db, user=user, request=request)
    refresh_token = _create_refresh_session(db, user_id=user.id, request=request)
    db.commit()
    db.refresh(user)

    access_token, access_expires_at = create_access_token(user_id=user.id, email=user.email)
    _set_refresh_cookie(response, refresh_token)
    return AuthResponse(
        access_token=access_token,
        access_token_expires_at=access_expires_at,
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin, response: Response, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    normalized_email = payload.email.strip().lower()
    try:
        enforce_auth_rate_limit(
            db,
            action="login",
            identifier=normalized_email,
            request=request,
            limit=settings.auth_login_rate_limit,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            _log_login_failure(request, email=normalized_email, reason="rate_limited")
        raise

    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if not user:
        _log_login_failure(request, email=normalized_email, reason="user_missing")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    if is_account_locked(user):
        _log_login_failure(request, email=normalized_email, reason="locked")
        db.commit()
        raise HTTPException(status_code=423, detail="account temporarily locked")

    if not verify_password(payload.password, user.password_hash):
        register_failed_login(db, user)
        reason = "locked" if is_account_locked(user) else "bad_password"
        _log_login_failure(request, email=normalized_email, reason=reason)
        db.commit()
        if reason == "locked":
            raise HTTPException(status_code=423, detail="account temporarily locked")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    now = utcnow()
    reset_failed_login_state(user)
    user.last_login = now
    if needs_password_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        user.password_changed_at = now

    refresh_token = _create_refresh_session(db, user_id=user.id, request=request)
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token, access_expires_at = create_access_token(user_id=user.id, email=user.email)
    _set_refresh_cookie(response, refresh_token)
    return AuthResponse(
        access_token=access_token,
        access_token_expires_at=access_expires_at,
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh_session(response: Response, request: Request, db: Session = Depends(get_db)) -> RefreshResponse:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing refresh token")

    enforce_auth_rate_limit(
        db,
        action="refresh",
        identifier=hash_token(refresh_token),
        request=request,
        limit=settings.auth_refresh_rate_limit,
    )

    session = db.query(RefreshSession).filter(RefreshSession.token_hash == hash_token(refresh_token)).first()
    if not session:
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")
    if session.revoked_at:
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="revoked refresh token")

    now = utcnow()
    expires_at = ensure_aware(session.expires_at)
    if expires_at is None or expires_at <= now:
        session.revoked_at = now
        session.last_used_at = now
        db.add(session)
        db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired refresh token")

    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        session.revoked_at = now
        session.last_used_at = now
        db.add(session)
        db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")

    session.revoked_at = now
    session.last_used_at = now
    user.last_login = now

    new_refresh_token = _create_refresh_session(
        db,
        user_id=user.id,
        request=request,
        rotated_from_session_id=session.id,
    )
    db.add(session)
    db.add(user)
    db.commit()
    access_token, access_expires_at = create_access_token(user_id=user.id, email=user.email)
    _set_refresh_cookie(response, new_refresh_token)
    return RefreshResponse(access_token=access_token, access_token_expires_at=access_expires_at)


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response, request: Request, db: Session = Depends(get_db)) -> LogoutResponse:
    session = _current_refresh_session(db, request)
    if session and not session.revoked_at:
        now = utcnow()
        session.revoked_at = now
        session.last_used_at = now
        db.add(session)
        db.commit()
    _clear_refresh_cookie(response)
    return LogoutResponse(success=True)


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> VerifyEmailResponse:
    token_row = consume_auth_action_token(db, token_type=EMAIL_VERIFICATION_TOKEN, token=payload.token)
    user = db.get(User, token_row.user_id)
    if not user or not user.is_active:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid token")
    if user.email_verified_at is not None:
        db.commit()
        return VerifyEmailResponse(status="already_verified", message="email already verified")
    else:
        user.email_verified_at = utcnow()
        db.add(user)
        db.commit()
        return VerifyEmailResponse(status="verified", message="email verified")


@router.post("/resend-verification", response_model=AuthMessageResponse)
def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthMessageResponse:
    enforce_auth_rate_limit(
        db,
        action="resend_verification",
        identifier=payload.email,
        request=request,
        limit=settings.auth_resend_verification_rate_limit,
    )
    user = db.query(User).filter(func.lower(User.email) == payload.email).first()
    if user and user.is_active and user.email_verified_at is None:
        _send_verification_email(db, user=user, request=request)
    db.commit()
    return AuthMessageResponse(message="if an account needs verification, a new email was sent")


@router.post("/password-reset/request", response_model=AuthMessageResponse)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthMessageResponse:
    enforce_auth_rate_limit(
        db,
        action="password_reset_request",
        identifier=payload.email,
        request=request,
        limit=settings.auth_password_reset_rate_limit,
    )
    user = db.query(User).filter(func.lower(User.email) == payload.email).first()
    if user and user.is_active:
        _send_password_reset_email(db, user=user, request=request)
    db.commit()
    return AuthMessageResponse(message="if an account exists, a password reset email was sent")


@router.post("/password-reset/confirm", response_model=AuthMessageResponse)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthMessageResponse:
    enforce_auth_rate_limit(
        db,
        action="password_reset_confirm",
        identifier=payload.token,
        request=request,
        limit=settings.auth_password_reset_rate_limit,
    )
    token_row = consume_auth_action_token(db, token_type=PASSWORD_RESET_TOKEN, token=payload.token)
    user = db.get(User, token_row.user_id)
    if not user or not user.is_active:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token")

    now = utcnow()
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = now
    user.email_verified_at = user.email_verified_at or now
    reset_failed_login_state(user)
    revoke_user_sessions(db, user_id=user.id, now=now)
    db.add(user)
    db.commit()
    return AuthMessageResponse(message="password reset complete")


@router.get("/sessions", response_model=SessionsResponse)
def list_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionsResponse:
    now = utcnow()
    current = _current_refresh_session(db, request)
    sessions = (
        db.query(RefreshSession)
        .filter(
            RefreshSession.user_id == current_user.id,
            RefreshSession.revoked_at.is_(None),
        )
        .order_by(RefreshSession.issued_at.desc())
        .all()
    )
    active_sessions = [
        session
        for session in sessions
        if ensure_aware(session.expires_at) is not None and ensure_aware(session.expires_at) > now
    ]
    return SessionsResponse(
        sessions=[
            SessionRead(
                id=session.id,
                issued_at=session.issued_at,
                expires_at=session.expires_at,
                last_used_at=session.last_used_at,
                user_agent=session.user_agent,
                ip_address=session.ip_address,
                is_current=current is not None and current.id == session.id,
            )
            for session in active_sessions
        ]
    )


@router.delete("/sessions/{session_id}", response_model=AuthMessageResponse)
def revoke_session(
    session_id: int,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthMessageResponse:
    session = db.get(RefreshSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    current = _current_refresh_session(db, request)
    now = utcnow()
    if not session.revoked_at:
        session.revoked_at = now
        session.last_used_at = now
        db.add(session)
        db.commit()
    if current and current.id == session.id:
        _clear_refresh_cookie(response)
    return AuthMessageResponse(message="session revoked")


@router.post("/logout-all", response_model=AuthMessageResponse)
def logout_all(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthMessageResponse:
    revoke_user_sessions(db, user_id=current_user.id)
    db.commit()
    _clear_refresh_cookie(response)
    return AuthMessageResponse(message="all sessions revoked")
