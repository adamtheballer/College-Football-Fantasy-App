from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from collegefootballfantasy_api.app.api.deps import require_verified_user
from collegefootballfantasy_api.app.core.config import Settings, settings
from collegefootballfantasy_api.app.main import app
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.app_review import AppReviewClaim
from collegefootballfantasy_api.app.services.app_review import claim_review
from conftest import TestingSessionLocal, engine

PAYLOAD = {"app_version": "1.0", "app_build": "123"}


@pytest.fixture(autouse=True)
def enable_review(monkeypatch):
    monkeypatch.setattr(settings, "ios_app_review_enabled", True)


def account(client, suffix="one"):
    response = client.post("/auth/signup", json={"first_name": "Review", "email": f"review-{suffix}@example.com", "password": "StrongPass123!"})
    assert response.status_code == 201
    payload = response.json()
    return payload["user"]["id"], {"Authorization": f"Bearer {payload['access_token']}", "Origin": "capacitor://localhost",
                                  "X-CFFB-Native-Session": "ios", "X-CFFB-Review-Account": str(payload["user"]["id"])}


def test_first_claim_persists_before_response_and_never_replays(client, db_session):
    user_id, headers = account(client)
    state = client.get("/app-review/state", headers=headers).json()
    assert state == {"account_id": user_id, "enabled": True, "review_request_claimed_at": None}
    first = client.post("/app-review/claim", headers=headers, json=PAYLOAD)
    assert first.status_code == 200
    assert first.json()["authorization"] == "granted"
    assert first.json()["review_request_claimed_at"]
    user = db_session.get(User, user_id)
    assert user.review_request_claimed_at is not None
    assert user.review_request_app_version == "1.0"
    assert user.review_request_app_build == "123"
    user.email = "changed@example.com"
    user.first_name = "Changed"
    db_session.commit()
    # Another device/build, lost response, logout/relogin, reinstall all use
    # the same immutable account. No request identifier can replay a grant.
    for build in ["123", "124", "999"]:
        response = client.post("/app-review/claim", headers=headers, json={**PAYLOAD, "app_build": build})
        assert response.json()["authorization"] == "already_claimed"
        assert response.json()["review_request_claimed_at"] == first.json()["review_request_claimed_at"]
    db_session.refresh(user)
    assert user.review_request_app_build == "123"


def test_default_disabled_and_flag_toggle_preserves_state(client, monkeypatch):
    assert Settings(_env_file=None).ios_app_review_enabled is False
    _, headers = account(client)
    monkeypatch.setattr(settings, "ios_app_review_enabled", False)
    result = client.post("/app-review/claim", headers=headers, json=PAYLOAD).json()
    assert result["authorization"] == "disabled" and result["review_request_claimed_at"] is None
    assert client.get("/health/runtime").json()["ios_app_review_enabled"] is False
    monkeypatch.setattr(settings, "ios_app_review_enabled", True)
    assert client.post("/app-review/claim", headers=headers, json=PAYLOAD).json()["authorization"] == "granted"
    monkeypatch.setattr(settings, "ios_app_review_enabled", False)
    assert client.get("/app-review/state", headers=headers).json()["review_request_claimed_at"]
    monkeypatch.setattr(settings, "ios_app_review_enabled", True)
    assert client.post("/app-review/claim", headers=headers, json=PAYLOAD).json()["authorization"] == "already_claimed"


@pytest.mark.parametrize("changes", [{"Origin": "https://www.collegefantasyfootball.org"}, {"Origin": "http://localhost:5173"}, {"Origin": ""}, {"X-CFFB-Native-Session": ""}, {"X-CFFB-Native-Session": "android"}])
def test_browser_cannot_consume(client, changes):
    _, headers = account(client)
    headers.update(changes)
    assert client.post("/app-review/claim", headers=headers, json=PAYLOAD).status_code == 403
    with TestingSessionLocal() as db:
        assert db.scalar(select(User.review_request_claimed_at)) is None


@pytest.mark.parametrize("token", ["", "bad-token"])
def test_guest_or_failed_auth_never_claims(client, token):
    _, headers = account(client)
    headers["Authorization"] = f"Bearer {token}" if token else ""
    assert client.post("/app-review/claim", headers=headers, json=PAYLOAD).status_code == 401


def test_required_verification_policy_is_respected(client):
    _, headers = account(client)
    def incomplete_verification():
        raise HTTPException(status_code=403, detail="verify email first")
    # Email verification is currently disabled by product policy. If that
    # existing dependency requires it, the review routes cannot bypass it.
    app.dependency_overrides[require_verified_user] = incomplete_verification
    assert client.post("/app-review/claim", headers=headers, json=PAYLOAD).status_code == 403


def test_account_switch_precondition_and_no_client_account_selector(client):
    first_id, first_headers = account(client, "first")
    second_id, second_headers = account(client, "second")
    assert first_id != second_id
    switched = {**second_headers, "X-CFFB-Review-Account": str(first_id)}
    assert client.post("/app-review/claim", headers=switched, json=PAYLOAD).status_code == 409
    assert client.post("/app-review/claim", headers=first_headers, json={**PAYLOAD, "account_id": second_id}).status_code == 422
    assert client.post("/app-review/claim", headers=first_headers, json=PAYLOAD).json()["authorization"] == "granted"
    assert client.get("/app-review/state", headers=second_headers).json()["review_request_claimed_at"] is None


@pytest.mark.parametrize("payload", [{"app_version": "", "app_build": "1"}, {"app_version": "1", "app_build": " "}, {"app_version": "a" * 81, "app_build": "1"}, {"app_version": "1"}])
def test_claim_metadata_validation(client, payload):
    _, headers = account(client)
    assert client.post("/app-review/claim", headers=headers, json=payload).status_code == 422


def test_database_rejects_partial_consumed_metadata(client, db_session):
    user_id, _ = account(client)
    user = db_session.get(User, user_id)
    user.review_request_app_build = "123"
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="PostgreSQL row-lock concurrency must run on a disposable PostgreSQL database")
def test_two_simultaneous_devices_receive_one_authorization(client):
    user_id, _ = account(client)
    barrier = Barrier(2)
    def device():
        with TestingSessionLocal() as db:
            barrier.wait(timeout=5)
            return claim_review(db, user_id, AppReviewClaim(**PAYLOAD)).authorization
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: device(), range(2)))
    assert sorted(results) == ["already_claimed", "granted"]
    with TestingSessionLocal() as db:
        assert db.get(User, user_id).review_request_claimed_at is not None
