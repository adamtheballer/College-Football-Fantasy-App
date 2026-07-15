from datetime import datetime, timedelta, timezone

import bcrypt

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.api.deps import require_verified_user
from collegefootballfantasy_api.app.core.security import (
    PASSWORD_HASH_ALGORITHM,
    create_access_token,
    generate_token,
    hash_password,
    needs_password_rehash,
    verify_password,
)
from collegefootballfantasy_api.app.models.refresh_session import RefreshSession
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.email_service import ConsoleEmailService, EmailPayload


STRONG_PASSWORD = "StrongPass123!"
LEGACY_PASSWORD = "secret123"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signup_user(client, suffix: str = "one") -> dict:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": STRONG_PASSWORD,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_signup_returns_ready_to_use_account_and_refresh_cookie(client, db_session):
    payload = signup_user(client, "signup")
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["access_token_expires_at"]
    assert payload["user"]["email"] == "coach-signup@example.com"
    assert payload["user"]["email_verified_at"] is not None
    assert settings.refresh_cookie_name in client.cookies
    user = db_session.get(User, payload["user"]["id"])
    assert user is not None
    assert user.email_verified_at is not None


def test_legacy_unverified_account_is_not_blocked_while_verification_is_disabled():
    user = User(
        first_name="Legacy",
        email="legacy-unverified@example.com",
        username="legacy-unverified",
        password_hash=hash_password(STRONG_PASSWORD),
        api_token=generate_token(32),
    )

    assert require_verified_user(user) is user


def test_email_verification_endpoints_are_not_exposed(client):
    assert client.post("/auth/verify-email", json={"token": "unused"}).status_code == 404
    assert client.post("/auth/resend-verification", json={"email": "coach@example.com"}).status_code == 404


def test_signup_normalizes_and_returns_username(client):
    response = client.post(
        "/auth/signup",
        json={
            "first_name": "Coach",
            "email": "username@example.com",
            "username": " Saturday Coach! ",
            "password": STRONG_PASSWORD,
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["username"] == "saturday-coach"


def test_signup_rejects_duplicate_username(client):
    first = client.post(
        "/auth/signup",
        json={
            "first_name": "Coach",
            "email": "username-one@example.com",
            "username": "Same Name",
            "password": STRONG_PASSWORD,
        },
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/auth/signup",
        json={
            "first_name": "Coach",
            "email": "username-two@example.com",
            "username": "same-name",
            "password": STRONG_PASSWORD,
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "username already registered"


def test_signup_rejects_password_under_12_chars(client):
    response = client.post(
        "/auth/signup",
        json={"first_name": "Coach", "email": "short@example.com", "password": "Short1!"},
    )
    assert response.status_code == 422


def test_signup_rejects_password_missing_uppercase(client):
    response = client.post(
        "/auth/signup",
        json={"first_name": "Coach", "email": "upper@example.com", "password": "lowercase123!"},
    )
    assert response.status_code == 422


def test_signup_rejects_password_missing_number(client):
    response = client.post(
        "/auth/signup",
        json={"first_name": "Coach", "email": "number@example.com", "password": "NoNumberHere!"},
    )
    assert response.status_code == 422


def test_signup_rejects_password_missing_special_character(client):
    response = client.post(
        "/auth/signup",
        json={"first_name": "Coach", "email": "special@example.com", "password": "NoSpecial123"},
    )
    assert response.status_code == 422


def test_signup_accepts_valid_strong_password(client):
    response = client.post(
        "/auth/signup",
        json={"first_name": "Coach", "email": "valid@example.com", "password": STRONG_PASSWORD},
    )
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "valid@example.com"


def test_signup_stores_hash_not_plaintext(client, db_session):
    signup_user(client, "stored")
    user = db_session.query(User).filter(User.email == "coach-stored@example.com").one()

    assert user.password_hash != STRONG_PASSWORD
    assert STRONG_PASSWORD not in user.password_hash
    assert user.password_hash.startswith(f"{PASSWORD_HASH_ALGORITHM}$")


def test_duplicate_email_rejected_case_insensitively(client):
    response = client.post(
        "/auth/signup",
        json={"first_name": "Coach", "email": "CaseEmail@example.com", "password": STRONG_PASSWORD},
    )
    assert response.status_code == 201

    duplicate = client.post(
        "/auth/signup",
        json={"first_name": "Coach", "email": " caseemail@EXAMPLE.com ", "password": STRONG_PASSWORD},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "email already registered"


def test_login_succeeds_only_with_exact_password(client):
    signup_user(client, "exact")

    good = client.post(
        "/auth/login",
        json={"email": " coach-exact@EXAMPLE.com ", "password": STRONG_PASSWORD},
    )
    assert good.status_code == 200

    bad = client.post(
        "/auth/login",
        json={"email": "coach-exact@example.com", "password": "StrongPass123?"},
    )
    assert bad.status_code == 401
    assert bad.json()["detail"] == "invalid credentials"


def test_login_with_missing_user_returns_invalid_credentials(client):
    response = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": STRONG_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


def test_wrong_password_increments_failed_attempts(client, db_session):
    signup_user(client, "wrong-password")

    response = client.post(
        "/auth/login",
        json={"email": "coach-wrong-password@example.com", "password": "WrongPass123!"},
    )

    assert response.status_code == 401
    db_session.expire_all()
    user = db_session.query(User).filter(User.email == "coach-wrong-password@example.com").one()
    assert user.failed_login_attempts == 1
    assert user.last_failed_login_at is not None


def test_failed_login_limit_locks_account(client, db_session):
    signup_user(client, "lock-limit")

    for _ in range(settings.auth_failed_login_limit - 1):
        response = client.post(
            "/auth/login",
            json={"email": "coach-lock-limit@example.com", "password": "WrongPass123!"},
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/auth/login",
        json={"email": "coach-lock-limit@example.com", "password": "WrongPass123!"},
    )

    assert locked_response.status_code == 423
    assert locked_response.json()["detail"] == "account temporarily locked"
    db_session.expire_all()
    user = db_session.query(User).filter(User.email == "coach-lock-limit@example.com").one()
    assert user.failed_login_attempts == settings.auth_failed_login_limit
    assert user.locked_until is not None


def test_locked_account_allows_correct_password_and_resets_lockout(client, db_session):
    user = User(
        first_name="Locked",
        email="locked@example.com",
        username="locked",
        password_hash=hash_password(STRONG_PASSWORD),
        api_token=generate_token(32),
        failed_login_attempts=settings.auth_failed_login_limit,
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "locked@example.com", "password": STRONG_PASSWORD},
    )

    assert response.status_code == 200
    db_session.expire_all()
    refreshed_user = db_session.query(User).filter(User.email == "locked@example.com").one()
    assert refreshed_user.failed_login_attempts == 0
    assert refreshed_user.locked_until is None


def test_login_rate_limit_returns_too_many_requests(client):
    original_limit = settings.auth_login_rate_limit
    try:
        settings.auth_login_rate_limit = 2
        for _ in range(settings.auth_login_rate_limit):
            response = client.post(
                "/auth/login",
                json={"email": "rate-limit@example.com", "password": STRONG_PASSWORD},
            )
            assert response.status_code == 401

        blocked = client.post(
            "/auth/login",
            json={"email": "rate-limit@example.com", "password": STRONG_PASSWORD},
        )

        assert blocked.status_code == 429
        assert blocked.json()["detail"] == "too many requests"
    finally:
        settings.auth_login_rate_limit = original_limit


def test_rate_limited_account_allows_correct_password(client, db_session):
    signup_user(client, "rate-limit-valid")
    original_limit = settings.auth_login_rate_limit
    try:
        settings.auth_login_rate_limit = 2
        for _ in range(settings.auth_login_rate_limit):
            response = client.post(
                "/auth/login",
                json={"email": "coach-rate-limit-valid@example.com", "password": "WrongPass123!"},
            )
            assert response.status_code == 401

        response = client.post(
            "/auth/login",
            json={"email": "coach-rate-limit-valid@example.com", "password": STRONG_PASSWORD},
        )

        assert response.status_code == 200
        db_session.expire_all()
        user = db_session.query(User).filter(User.email == "coach-rate-limit-valid@example.com").one()
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
    finally:
        settings.auth_login_rate_limit = original_limit


def test_password_hashes_are_versioned_and_constant_time_verifiable():
    stored = hash_password(STRONG_PASSWORD)
    assert stored.startswith(f"{PASSWORD_HASH_ALGORITHM}$")
    assert verify_password(STRONG_PASSWORD, stored) is True
    assert verify_password("wrong", stored) is False
    assert needs_password_rehash(stored) is False


def test_legacy_password_hashes_verify_but_require_rehash():
    legacy = "YWFhYWFhYWFhYWFhYWFhYQ==$LrogHhynYTZ+hDQlQR3OlxFU/vcPWPRb0AnWTRxIVRA="
    assert verify_password(LEGACY_PASSWORD, legacy) is True
    assert needs_password_rehash(legacy) is True


def test_legacy_bcrypt_hashes_verify_but_require_rehash():
    legacy = bcrypt.hashpw(LEGACY_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    assert verify_password(LEGACY_PASSWORD, legacy) is True
    assert verify_password("wrong", legacy) is False
    assert needs_password_rehash(legacy) is True


def test_legacy_pbkdf2_hash_rehashes_to_argon2_on_login(client, db_session):
    legacy_hash = "YWFhYWFhYWFhYWFhYWFhYQ==$LrogHhynYTZ+hDQlQR3OlxFU/vcPWPRb0AnWTRxIVRA="
    user = User(
        first_name="Legacy",
        email="legacy@example.com",
        username="legacy",
        password_hash=legacy_hash,
        api_token=generate_token(32),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": " LEGACY@example.com ", "password": LEGACY_PASSWORD},
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed_user = db_session.query(User).filter(User.email == "legacy@example.com").one()
    assert refreshed_user.password_hash != legacy_hash
    assert refreshed_user.password_hash.startswith(f"{PASSWORD_HASH_ALGORITHM}$")
    assert verify_password(LEGACY_PASSWORD, refreshed_user.password_hash) is True
    assert needs_password_rehash(refreshed_user.password_hash) is False


def test_legacy_bcrypt_hash_rehashes_to_argon2_on_login(client, db_session):
    legacy_hash = bcrypt.hashpw(LEGACY_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(
        first_name="Bcrypt",
        email="bcrypt@example.com",
        username="bcrypt",
        password_hash=legacy_hash,
        api_token=generate_token(32),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": " BCRYPT@example.com ", "password": LEGACY_PASSWORD},
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed_user = db_session.query(User).filter(User.email == "bcrypt@example.com").one()
    assert refreshed_user.password_hash != legacy_hash
    assert refreshed_user.password_hash.startswith(f"{PASSWORD_HASH_ALGORITHM}$")
    assert verify_password(LEGACY_PASSWORD, refreshed_user.password_hash) is True
    assert needs_password_rehash(refreshed_user.password_hash) is False


def test_successful_login_resets_failed_attempts_and_expired_lockout(client, db_session):
    user = User(
        first_name="Returning",
        email="returning@example.com",
        username="returning",
        password_hash=hash_password(STRONG_PASSWORD),
        api_token=generate_token(32),
        failed_login_attempts=settings.auth_failed_login_limit,
        locked_until=datetime.now(timezone.utc) - timedelta(minutes=1),
        last_login=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "returning@example.com", "password": STRONG_PASSWORD},
    )

    assert response.status_code == 200
    db_session.expire_all()
    refreshed_user = db_session.query(User).filter(User.email == "returning@example.com").one()
    assert refreshed_user.failed_login_attempts == 0
    assert refreshed_user.locked_until is None
    assert refreshed_user.last_login is not None


def test_auth_me_returns_current_authenticated_user(client):
    payload = signup_user(client, "me")
    response = client.get("/auth/me", headers=auth_headers(payload["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == payload["user"]["id"]
    assert response.json()["email"] == "coach-me@example.com"


def test_login_token_survives_page_bootstrap_through_auth_me(client):
    signup_payload = signup_user(client, "bootstrap")

    login_response = client.post(
        "/auth/login",
        json={"email": "coach-bootstrap@example.com", "password": STRONG_PASSWORD},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["access_token"]
    assert login_payload["user"]["id"] == signup_payload["user"]["id"]

    bootstrap_response = client.get("/auth/me", headers=auth_headers(login_payload["access_token"]))

    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["id"] == signup_payload["user"]["id"]
    assert bootstrap_response.json()["email"] == "coach-bootstrap@example.com"


def test_auth_me_requires_authentication(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "missing auth token"


def test_console_email_service_does_not_log_password_reset_token(caplog):
    service = ConsoleEmailService()
    payload = EmailPayload(
        to_email="coach@example.com",
        subject="Reset password",
        body="Reset your password: http://localhost:8080/password-reset/confirm?token=sensitive-token",
    )

    service.send(payload)

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "sensitive-token" not in logged
    assert "coach@example.com" in logged


def test_local_dev_cors_allows_dynamic_vite_port(client):
    response = client.options(
        "/auth/signup",
        headers={
            "Origin": "http://localhost:8083",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8083"


def test_protected_route_accepts_bearer_access_token(client):
    payload = signup_user(client, "bearer")
    response = client.get("/leagues", headers=auth_headers(payload["access_token"]))
    assert response.status_code == 200


def test_protected_route_rejects_missing_token(client):
    response = client.get("/leagues")
    assert response.status_code == 401
    assert response.json()["detail"] == "missing auth token"


def test_protected_route_rejects_expired_access_token(client):
    payload = signup_user(client, "expired")
    original_ttl = settings.jwt_access_token_ttl_minutes
    try:
        settings.jwt_access_token_ttl_minutes = -1
        expired_token, _ = create_access_token(user_id=payload["user"]["id"], email=payload["user"]["email"])
    finally:
        settings.jwt_access_token_ttl_minutes = original_ttl

    response = client.get("/leagues", headers=auth_headers(expired_token))
    assert response.status_code == 401
    assert response.json()["detail"] == "expired access token"


def test_refresh_rotates_and_revokes_previous_session(client, db_session):
    signup_payload = signup_user(client, "refresh")
    first_refresh_cookie = client.cookies.get(settings.refresh_cookie_name)
    assert first_refresh_cookie

    first_response = client.post("/auth/refresh")
    assert first_response.status_code == 200
    assert first_response.json()["access_token"]

    second_cookie = client.cookies.get(settings.refresh_cookie_name)
    assert second_cookie
    assert second_cookie != first_refresh_cookie

    old_session = (
        db_session.query(RefreshSession)
        .filter(RefreshSession.token_hash.isnot(None))
        .order_by(RefreshSession.id.asc())
        .first()
    )
    assert old_session is not None
    assert old_session.revoked_at is not None

    revoked_response = client.post(
        "/auth/refresh",
        cookies={settings.refresh_cookie_name: first_refresh_cookie},
    )
    assert revoked_response.status_code == 401
    assert revoked_response.json()["detail"] == "revoked refresh token"

    valid_response = client.post(
        "/auth/refresh",
        cookies={settings.refresh_cookie_name: second_cookie},
    )
    assert valid_response.status_code == 200
    assert valid_response.json()["access_token"] != signup_payload["access_token"]


def test_logout_revokes_session_and_clears_cookie(client, db_session):
    signup_user(client, "logout")
    refresh_cookie = client.cookies.get(settings.refresh_cookie_name)
    assert refresh_cookie

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["success"] is True
    assert settings.refresh_cookie_name not in client.cookies

    session_row = db_session.query(RefreshSession).first()
    assert session_row is not None
    assert session_row.revoked_at is not None

    refresh_after_logout = client.post(
        "/auth/refresh",
        cookies={settings.refresh_cookie_name: refresh_cookie},
    )
    assert refresh_after_logout.status_code == 401
    assert refresh_after_logout.json()["detail"] == "revoked refresh token"
