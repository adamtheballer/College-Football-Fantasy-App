from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import (
    PASSWORD_HASH_ALGORITHM,
    create_access_token,
    hash_password,
    needs_password_rehash,
    verify_password,
)
from collegefootballfantasy_api.app.models.refresh_session import RefreshSession


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signup_user(client, suffix: str = "one") -> dict:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_signup_returns_access_token_and_refresh_cookie(client):
    payload = signup_user(client, "signup")
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["access_token_expires_at"]
    assert payload["user"]["email"] == "coach-signup@example.com"
    assert settings.refresh_cookie_name in client.cookies


def test_signup_normalizes_and_returns_username(client):
    response = client.post(
        "/auth/signup",
        json={
            "first_name": "Coach",
            "email": "username@example.com",
            "username": " Saturday Coach! ",
            "password": "secret123",
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
            "password": "secret123",
        },
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/auth/signup",
        json={
            "first_name": "Coach",
            "email": "username-two@example.com",
            "username": "same-name",
            "password": "secret123",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "username already registered"


def test_password_hashes_are_versioned_and_constant_time_verifiable():
    stored = hash_password("secret123")
    assert stored.startswith(f"{PASSWORD_HASH_ALGORITHM}$")
    assert verify_password("secret123", stored) is True
    assert verify_password("wrong", stored) is False
    assert needs_password_rehash(stored) is False


def test_legacy_password_hashes_verify_but_require_rehash():
    legacy = "YWFhYWFhYWFhYWFhYWFhYQ==$LrogHhynYTZ+hDQlQR3OlxFU/vcPWPRb0AnWTRxIVRA="
    assert verify_password("secret123", legacy) is True
    assert needs_password_rehash(legacy) is True


def test_auth_me_returns_current_authenticated_user(client):
    payload = signup_user(client, "me")
    response = client.get("/auth/me", headers=auth_headers(payload["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == payload["user"]["id"]
    assert response.json()["email"] == "coach-me@example.com"


def test_auth_me_requires_authentication(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "missing auth token"


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
