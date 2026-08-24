from __future__ import annotations

import re
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.core.config import TRUSTED_NATIVE_CORS_ORIGINS, settings
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
from collegefootballfantasy_api.app.models.beta_access import BetaAccessCode
from collegefootballfantasy_api.app.models.refresh_session import RefreshSession
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.auth import (
    AccountDeletionRequest,
    AuthMessageResponse,
    AuthResponse,
    AuthenticatedPasswordChange,
    LogoutResponse,
    PasswordResetWithCurrentPassword,
    PasswordResetCompleteResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetValidate,
    PasswordResetValidateResponse,
    RefreshResponse,
    SessionRead,
    SessionsResponse,
    UserCreate,
    UserLogin,
    UserRead,
    UserProfileUpdate,
)
from collegefootballfantasy_api.app.services.auth_security import (
    enforce_auth_rate_limit,
    ensure_aware,
    is_account_locked,
    register_failed_login,
    request_ip,
    reset_failed_login_state,
    revoke_user_sessions,
    utcnow,
)
from collegefootballfantasy_api.app.services.account_deletion import permanently_delete_user_account
from collegefootballfantasy_api.app.services.beta_access import (
    GENERIC_MISMATCH_MESSAGE,
    consume_beta_access_reservation,
    redeem_beta_access,
    release_beta_access_reservation,
)
from collegefootballfantasy_api.app.services.content_moderation import moderate_user_text
from collegefootballfantasy_api.app.services.password_change import (
    PasswordChangeCredentialError,
    PasswordChangeValidationError,
    change_user_password,
)
from collegefootballfantasy_api.app.services.password_reset import (
    GENERIC_RESET_MESSAGE,
    INVALID_RESET_TOKEN_MESSAGE,
    complete_reset,
    create_reset_request,
    record_invalid_attempt,
    validate_reset_token,
)

router = APIRouter()
logger = logging.getLogger(__name__)
PASSWORD_CHANGE_CREDENTIAL_ERROR = "Unable to reset password with the provided credentials."


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


def _refresh_cookie_samesite(request: Request | None) -> str:
    """Keep native Capacitor refresh sessions usable after access-token expiry.

    The web app is same-site behind the Vercel /api proxy and keeps the
    configured default. Capacitor is a separate ``capacitor://localhost``
    origin, so production secure cookies must explicitly allow that trusted
    cross-site request.
    """

    if (
        request is not None
        and settings.refresh_cookie_secure
        and request.headers.get("origin") in TRUSTED_NATIVE_CORS_ORIGINS
    ):
        return "none"
    return settings.refresh_cookie_samesite


def _set_refresh_cookie(response: Response, refresh_token: str, request: Request | None = None) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=_refresh_cookie_samesite(request),
        path="/",
        domain=settings.refresh_cookie_domain,
    )
    # This contains no credential or user identifier. It merely lets the web
    # client decide whether a silent refresh is worth attempting when browser
    # storage was cleared but the HTTP-only refresh cookie is still valid.
    response.set_cookie(
        key=settings.refresh_presence_cookie_name,
        value="1",
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=False,
        secure=settings.refresh_cookie_secure,
        samesite=_refresh_cookie_samesite(request),
        path="/",
        domain=settings.refresh_cookie_domain,
    )


def _clear_refresh_cookie(response: Response, request: Request | None = None) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=_refresh_cookie_samesite(request),
        path="/",
        domain=settings.refresh_cookie_domain,
    )
    response.delete_cookie(
        key=settings.refresh_presence_cookie_name,
        httponly=False,
        secure=settings.refresh_cookie_secure,
        samesite=_refresh_cookie_samesite(request),
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


def _log_login_failure(request: Request, *, email: str, reason: str) -> None:
    local, separator, domain = email.partition("@")
    redacted_email = f"{local[:1]}***{separator}{domain}" if separator else "***"
    logger.info(
        "auth_login_failed",
        extra={
            "email": redacted_email,
            "failure_reason": reason,
            "request_ip_hash": hash_token(request_ip(request) or "") if request_ip(request) else None,
        },
    )


def _complete_successful_login(
    *,
    db: Session,
    user: User,
    password: str,
    response: Response,
    request: Request,
    beta_access_code: BetaAccessCode | None = None,
) -> AuthResponse:
    now = utcnow()
    reset_failed_login_state(user)
    user.last_login = now
    if needs_password_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        user.password_changed_at = now

    refresh_token = _create_refresh_session(db, user_id=user.id, request=request)
    if beta_access_code:
        # A registered member must prove both their account password and the
        # exact assigned e-mail/code pair before this entitlement is linked.
        redeem_beta_access(db, code=beta_access_code, user=user, request=request)
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token, access_expires_at = create_access_token(
        user_id=user.id,
        email=user.email,
        auth_version=user.auth_version,
    )
    _set_refresh_cookie(response, refresh_token, request)
    return AuthResponse(
        access_token=access_token,
        access_token_expires_at=access_expires_at,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def current_user_profile(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
def update_current_user_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Update only the signed-in manager's beta profile fields."""

    fields_set = payload.model_fields_set
    if "first_name" in fields_set:
        next_name = moderate_user_text(
            db,
            actor_user_id=current_user.id,
            field_name="manager_name",
            value=payload.first_name,
            required=True,
        ) or current_user.first_name
        if next_name != current_user.first_name:
            now = utcnow()
            available_at = current_user.manager_name_change_available_at
            if available_at is not None and ensure_aware(available_at) > now:
                seconds_remaining = max(1, int((ensure_aware(available_at) - now).total_seconds()))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Manager name can only be changed once every 7 days.",
                    headers={"Retry-After": str(seconds_remaining)},
                )
            current_user.first_name = next_name
            current_user.manager_name_changed_at = now
            # League, roster, matchup, draft, chat, and rivalry reads all
            # resolve the manager's current team through this record. Keep the
            # denormalized owner name in sync and refresh generated ``Name's
            # Team`` labels, including labels made stale by earlier releases.
            # A non-standard team name is a deliberate custom team name and is
            # therefore preserved.
            owned_teams = (
                db.query(Team)
                .filter(Team.owner_user_id == current_user.id)
                .all()
            )
            for team in owned_teams:
                team.owner_name = next_name
                if team.name.endswith("'s Team"):
                    team.name = f"{next_name}'s Team"
    if "avatar_url" in fields_set:
        current_user.avatar_url = payload.avatar_url
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserRead.model_validate(current_user)


@router.delete("/me", response_model=AuthMessageResponse)
def delete_current_user_account(
    payload: AccountDeletionRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthMessageResponse:
    """Permanently delete the authenticated account and its personal data."""

    enforce_auth_rate_limit(
        db,
        action="account_deletion",
        identifier=f"user:{current_user.id}",
        request=request,
        limit=settings.auth_password_change_rate_limit,
    )
    if not verify_password(payload.current_password, current_user.password_hash):
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PASSWORD_CHANGE_CREDENTIAL_ERROR)

    try:
        permanently_delete_user_account(db, user=current_user)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("account_deletion_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete your account right now.",
        ) from exc

    _clear_refresh_cookie(response, request)
    return AuthMessageResponse(message="account deleted")


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, response: Response, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    payload.first_name = moderate_user_text(
        db, actor_user_id=None, field_name="manager_name", value=payload.first_name, required=True
    ) or ""
    payload.username = moderate_user_text(
        db, actor_user_id=None, field_name="manager_nickname", value=payload.username
    )
    beta_access_code = None
    signup_email = payload.email
    # An Early Access code is optional: it records a future one-year Pro
    # benefit, but must never decide whether someone can create an account.
    if payload.beta_access_reservation:
        if not settings.beta_access_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_MISMATCH_MESSAGE)
        beta_access_code = consume_beta_access_reservation(db, token=payload.beta_access_reservation)
        if beta_access_code.email != signup_email:
            release_beta_access_reservation(db, code=beta_access_code, request=request)
            db.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_MISMATCH_MESSAGE)

    try:
        enforce_auth_rate_limit(
            db,
            action="signup",
            identifier=signup_email,
            request=request,
            limit=settings.auth_signup_rate_limit,
        )
        existing = db.query(User).filter(func.lower(User.email) == signup_email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

        username = _normalize_username(payload.username, fallback=signup_email.split("@", 1)[0])
        if payload.username and db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already registered")

        now = utcnow()
        user = User(
            first_name=payload.first_name,
            email=signup_email,
            username=_unique_username(db, username),
            password_hash=hash_password(payload.password),
            api_token=generate_token(32),
            last_login=now,
            password_changed_at=now,
            email_verified_at=now,
        )
        db.add(user)
        db.flush()
        refresh_token = _create_refresh_session(db, user_id=user.id, request=request)
        if beta_access_code:
            redeem_beta_access(db, code=beta_access_code, user=user, request=request)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if beta_access_code:
            refreshed_code = db.query(BetaAccessCode).filter(BetaAccessCode.id == beta_access_code.id).one()
            release_beta_access_reservation(db, code=refreshed_code, request=request)
            db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="account could not be created") from exc
    except HTTPException:
        if beta_access_code:
            release_beta_access_reservation(db, code=beta_access_code, request=request)
            db.commit()
        raise
    db.refresh(user)

    access_token, access_expires_at = create_access_token(
        user_id=user.id,
        email=user.email,
        auth_version=user.auth_version,
    )
    _set_refresh_cookie(response, refresh_token, request)
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
            user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
            if user and verify_password(payload.password, user.password_hash):
                return _complete_successful_login(
                    db=db,
                    user=user,
                    password=payload.password,
                    response=response,
                    request=request,
                )
            _log_login_failure(request, email=normalized_email, reason="rate_limited")
        raise

    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if not user:
        _log_login_failure(request, email=normalized_email, reason="user_missing")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        if is_account_locked(user):
            _log_login_failure(request, email=normalized_email, reason="locked")
            db.commit()
            raise HTTPException(status_code=423, detail="account temporarily locked")
        register_failed_login(db, user)
        reason = "locked" if is_account_locked(user) else "bad_password"
        _log_login_failure(request, email=normalized_email, reason=reason)
        db.commit()
        if reason == "locked":
            raise HTTPException(status_code=423, detail="account temporarily locked")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    beta_access_code = None
    # Signing in never requires a code.  A reservation is accepted only when a
    # returning user voluntarily claims their future one-year Pro benefit.
    if payload.beta_access_reservation:
        if not settings.beta_access_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_MISMATCH_MESSAGE)
        beta_access_code = consume_beta_access_reservation(db, token=payload.beta_access_reservation)
        if beta_access_code.email != normalized_email:
            # Preserve a valid reservation for its intended owner, but never
            # attach it to a different signed-in account.
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_MISMATCH_MESSAGE)

    return _complete_successful_login(
        db=db,
        user=user,
        password=payload.password,
        response=response,
        request=request,
        beta_access_code=beta_access_code,
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
        _clear_refresh_cookie(response, request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired refresh token")

    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        session.revoked_at = now
        session.last_used_at = now
        db.add(session)
        db.commit()
        _clear_refresh_cookie(response, request)
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
    access_token, access_expires_at = create_access_token(
        user_id=user.id,
        email=user.email,
        auth_version=user.auth_version,
    )
    _set_refresh_cookie(response, new_refresh_token, request)
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
    _clear_refresh_cookie(response, request)
    return LogoutResponse(success=True)


def _enforce_password_reset_request_limits(db: Session, *, email: str, request: Request) -> None:
    enforce_auth_rate_limit(
        db,
        action="password_reset_email_cooldown",
        identifier=email,
        request=request,
        limit=1,
        window_seconds=settings.password_reset_request_cooldown_seconds,
        include_ip=False,
    )
    enforce_auth_rate_limit(
        db,
        action="password_reset_email_hour",
        identifier=email,
        request=request,
        limit=settings.password_reset_max_per_email_per_hour,
        window_minutes=60,
        include_ip=False,
    )
    enforce_auth_rate_limit(
        db,
        action="password_reset_ip_hour",
        identifier=None,
        request=request,
        limit=settings.password_reset_max_per_ip_per_hour,
        window_minutes=60,
        include_ip=True,
    )


@router.post("/password-reset/request", response_model=AuthMessageResponse, status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthMessageResponse:
    """Always return the same accepted response so email ownership stays private."""
    if not settings.password_reset_enabled:
        return AuthMessageResponse(message=GENERIC_RESET_MESSAGE)
    try:
        _enforce_password_reset_request_limits(db, email=payload.email, request=request)
        user = _active_user_for_normalized_email(db, payload.email)
        if user:
            create_reset_request(db, user=user, request=request)
        # Unknown accounts still perform a keyed digest operation to avoid a trivial timing split.
        else:
            validate_reset_token(db, "padding-token-for-enumeration-resistance")
        db.commit()
    except HTTPException:
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("password_reset_request_failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to process request") from exc
    return AuthMessageResponse(message=GENERIC_RESET_MESSAGE)


@router.post("/password-reset/request-for-current-user", response_model=AuthMessageResponse, status_code=status.HTTP_202_ACCEPTED)
def request_password_reset_for_current_user(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthMessageResponse:
    if not settings.password_reset_enabled:
        return AuthMessageResponse(message=GENERIC_RESET_MESSAGE)
    try:
        _enforce_password_reset_request_limits(db, email=current_user.email, request=request)
        create_reset_request(db, user=current_user, request=request)
        db.commit()
    except HTTPException:
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("password_reset_current_user_request_failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to process request") from exc
    return AuthMessageResponse(message=GENERIC_RESET_MESSAGE)


@router.post("/password-reset/validate", response_model=PasswordResetValidateResponse)
def validate_password_reset(
    payload: PasswordResetValidate,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetValidateResponse:
    try:
        enforce_auth_rate_limit(
            db,
            action="password_reset_validate",
            identifier=payload.token,
            request=request,
            limit=settings.password_reset_confirm_rate_limit,
            window_minutes=15,
        )
        valid = settings.password_reset_enabled and validate_reset_token(db, payload.token) is not None
        db.commit()
        return PasswordResetValidateResponse(valid=valid)
    except HTTPException:
        db.commit()
        return PasswordResetValidateResponse(valid=False)


@router.post("/password-reset/confirm", response_model=PasswordResetCompleteResponse)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetCompleteResponse:
    try:
        enforce_auth_rate_limit(
            db,
            action="password_reset_confirm",
            identifier=payload.token,
            request=request,
            limit=settings.password_reset_confirm_rate_limit,
            window_minutes=15,
        )
        if not settings.password_reset_enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_TOKEN_MESSAGE)
        complete_reset(
            db,
            token=payload.token,
            new_password=payload.new_password,
            confirm_password=payload.confirm_password,
            request=request,
        )
        db.commit()
        return PasswordResetCompleteResponse()
    except HTTPException as exc:
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            record_invalid_attempt(db, request=request)
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("password_reset_confirm_failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to reset password right now.") from exc


def _active_user_for_normalized_email(db: Session, normalized_email: str) -> User | None:
    users = (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email, User.is_active.is_(True))
        .limit(2)
        .all()
    )
    return users[0] if len(users) == 1 else None


def _password_change_validation_error(error: PasswordChangeValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


@router.post("/reset-password-with-current-password", response_model=AuthMessageResponse)
def reset_password_with_current_password(
    payload: PasswordResetWithCurrentPassword,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthMessageResponse:
    enforce_auth_rate_limit(
        db,
        action="password_reset_with_current_password",
        identifier=payload.email,
        request=request,
        limit=settings.auth_password_change_rate_limit,
    )
    user = _active_user_for_normalized_email(db, payload.email)
    if not user:
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PASSWORD_CHANGE_CREDENTIAL_ERROR)

    try:
        change_user_password(
            db,
            user=user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            confirm_new_password=payload.confirm_new_password,
        )
        db.commit()
    except PasswordChangeCredentialError:
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PASSWORD_CHANGE_CREDENTIAL_ERROR)
    except PasswordChangeValidationError as exc:
        db.commit()
        raise _password_change_validation_error(exc) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("password_reset_with_current_password_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to reset password right now.",
        ) from exc

    _clear_refresh_cookie(response, request)
    return AuthMessageResponse(message="password reset complete")


@router.post("/change-password", response_model=AuthMessageResponse)
def change_password(
    payload: AuthenticatedPasswordChange,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthMessageResponse:
    enforce_auth_rate_limit(
        db,
        action="authenticated_password_change",
        identifier=f"user:{current_user.id}",
        request=request,
        limit=settings.auth_password_change_rate_limit,
    )
    try:
        change_user_password(
            db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            confirm_new_password=payload.confirm_new_password,
        )
        db.commit()
    except PasswordChangeCredentialError:
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PASSWORD_CHANGE_CREDENTIAL_ERROR)
    except PasswordChangeValidationError as exc:
        db.commit()
        raise _password_change_validation_error(exc) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("authenticated_password_change_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to reset password right now.",
        ) from exc

    _clear_refresh_cookie(response, request)
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
        _clear_refresh_cookie(response, request)
    return AuthMessageResponse(message="session revoked")


@router.post("/logout-all", response_model=AuthMessageResponse)
def logout_all(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthMessageResponse:
    revoke_user_sessions(db, user_id=current_user.id)
    db.commit()
    _clear_refresh_cookie(response, request)
    return AuthMessageResponse(message="all sessions revoked")
