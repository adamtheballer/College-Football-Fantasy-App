from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from api.app.api.deps import get_current_user
from api.app.core.config import settings
from api.app.core.security import (
    create_access_token,
    generate_refresh_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from api.app.db.session import get_db
from api.app.models.refresh_session import RefreshSession
from api.app.models.user import User
from api.app.schemas.auth import (
    AuthResponse,
    LogoutResponse,
    RefreshResponse,
    UserCreate,
    UserLogin,
    UserRead,
)
from api.app.services.auth_rate_limit import (
    assert_login_not_rate_limited,
    clear_failed_logins,
    record_failed_login,
)

router = APIRouter()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


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
    now = _now_utc()
    db.add(
        RefreshSession(
            user_id=user_id,
            token_hash=hash_token(refresh_token),
            issued_at=now,
            expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
            rotated_from_session_id=rotated_from_session_id,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    )
    return refresh_token


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, response: Response, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")
    now = _now_utc()
    user = User(
        first_name=payload.first_name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        api_token=generate_token(32),
        last_login=now,
    )
    db.add(user)
    db.flush()
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
    assert_login_not_rate_limited(request, payload.email)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        record_failed_login(request, payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    clear_failed_logins(request, payload.email)
    now = _now_utc()
    user.last_login = now
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

    session = db.query(RefreshSession).filter(RefreshSession.token_hash == hash_token(refresh_token)).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")
    if session.revoked_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="revoked refresh token")

    now = _now_utc()
    if _as_utc(session.expires_at) <= now:
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
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        session = db.query(RefreshSession).filter(RefreshSession.token_hash == hash_token(refresh_token)).first()
        if session and not session.revoked_at:
            now = _now_utc()
            session.revoked_at = now
            session.last_used_at = now
            db.add(session)
            db.commit()
    _clear_refresh_cookie(response)
    return LogoutResponse(success=True)
