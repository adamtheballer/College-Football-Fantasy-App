from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import create_access_token
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
