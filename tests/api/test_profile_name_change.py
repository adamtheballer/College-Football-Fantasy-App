from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from conftest import TestingSessionLocal, engine
from collegefootballfantasy_api.app.core.name_change import next_name_change_at
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.auth import UserProfileUpdate
from collegefootballfantasy_api.app.schemas.app_review import AppReviewClaim
from collegefootballfantasy_api.app.services import profile_names
from collegefootballfantasy_api.app.services.app_review import claim_review

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(profile_names, "server_now", lambda db: NOW)


def account(client, suffix="one"):
    payload = client.post("/auth/signup", json={"first_name": "Old Manager", "email": f"name-{suffix}@example.com", "password": "StrongPass123!"}).json()
    return payload["user"]["id"], {"Authorization": f"Bearer {payload['access_token']}"}


def set_changed(user_id, changed_at, avatar=None):
    with TestingSessionLocal() as db:
        user = db.get(User, user_id)
        user.manager_name_changed_at = changed_at
        if avatar is not None: user.avatar_url = avatar
        db.commit()


@pytest.mark.parametrize("hours_ago", [None, 192, 168])
def test_no_previous_expired_and_exact_168_hours_succeed(client, hours_ago):
    user_id, headers = account(client)
    set_changed(user_id, NOW - timedelta(hours=hours_ago) if hours_ago else None)
    state = client.get("/auth/me/name-change-eligibility", headers=headers).json()
    assert state["server_time"] == "2026-10-13T12:00:00Z"
    assert state["can_change_name"] and state["remaining_wait_seconds"] == 0
    response = client.patch("/auth/me", headers=headers, json={"first_name": "New Manager"})
    assert response.status_code == 200
    assert datetime.fromisoformat(response.json()["manager_name_changed_at"]) == NOW
    assert datetime.fromisoformat(response.json()["manager_name_change_available_at"]) == NOW + timedelta(hours=168)
    reopened = client.get("/auth/me/name-change-eligibility", headers=headers).json()
    assert reopened["current_name"] == "New Manager" and reopened["remaining_wait_seconds"] == 604800


@pytest.mark.parametrize("seconds_before, expected", [(1, 1), (0.0001, 1), (1.0001, 2), (3600, 3600)])
def test_before_expiration_rejects_with_ceiling_and_complete_server_timing(client, seconds_before, expected):
    user_id, headers = account(client)
    last = NOW - timedelta(hours=168) + timedelta(seconds=seconds_before)
    set_changed(user_id, last)
    response = client.patch("/auth/me", headers=headers, json={"first_name": "Rejected Manager"})
    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["code"] == "NAME_CHANGE_COOLDOWN"
    assert not detail["can_change_name"] and detail["remaining_wait_seconds"] == expected
    assert int(response.headers["retry-after"]) == expected
    assert datetime.fromisoformat(detail["last_successful_change_at"]) == last
    assert datetime.fromisoformat(detail["next_eligible_at"]) == last + timedelta(hours=168)
    assert detail["server_time"] == "2026-10-13T12:00:00Z"
    with TestingSessionLocal() as db:
        user = db.get(User, user_id)
        assert user.first_name == "Old Manager"
        stored = user.manager_name_changed_at
        # PostgreSQL may return the session's Eastern offset; replacing that
        # offset changes the instant. SQLite alone needs the naive UTC fallback.
        assert (stored if stored.tzinfo else stored.replace(tzinfo=timezone.utc)) == last


def test_expired_name_only_save_does_not_resend_invalid_unchanged_legacy_avatar(client):
    user_id, headers = account(client)
    set_changed(user_id, NOW - timedelta(hours=192), "http://legacy.example.com/avatar.jpg")
    # Reproduces the former Settings payload: this is validation, not cooldown.
    bad = client.patch("/auth/me", headers=headers, json={"first_name": "New Manager", "avatar_url": "http://legacy.example.com/avatar.jpg"})
    assert bad.status_code == 422
    assert bad.json()["detail"][0]["loc"] == ["body", "avatar_url"]
    good = client.patch("/auth/me", headers=headers, json={"first_name": "New Manager"})
    assert good.status_code == 200 and good.json()["first_name"] == "New Manager"
    assert good.json()["avatar_url"] == "http://legacy.example.com/avatar.jpg"


def test_same_saved_name_duplicate_and_unrelated_edits_do_not_extend_cooldown(client, monkeypatch):
    user_id, headers = account(client)
    changed = client.patch("/auth/me", headers=headers, json={"first_name": "New Manager"}).json()["manager_name_changed_at"]
    monkeypatch.setattr(profile_names, "server_now", lambda db: NOW + timedelta(hours=1))
    for payload in ({"first_name": "New Manager"}, {"first_name": " New Manager "}, {"avatar_url": "https://images.example.com/new.jpg"}):
        response = client.patch("/auth/me", headers=headers, json=payload)
        assert response.status_code == 200 and response.json()["manager_name_changed_at"] == changed
    monkeypatch.setattr(settings, "ios_app_review_enabled", True)
    # This test isolates profile cooldown from the review receipt mutation.
    from collegefootballfantasy_api.app.services import app_review
    monkeypatch.setattr(app_review, "meaningful_use", lambda db, uid: True)
    with TestingSessionLocal() as db:
        assert claim_review(db, user_id, AppReviewClaim(app_version="1", app_build="local")).authorization == "granted"
    response = client.get("/auth/me", headers=headers).json()
    assert response["manager_name_changed_at"] == changed
    assert client.post("/auth/login", json={"email": "name-one@example.com", "password": "StrongPass123!"}).status_code == 200
    assert client.get("/auth/me", headers=headers).json()["manager_name_changed_at"] == changed


@pytest.mark.parametrize("payload", [{"first_name": ""}, {"first_name": "a" * 51}, {"first_name": "Valid", "avatar_url": "bad-url"}])
def test_invalid_submission_never_changes_timestamp(client, payload):
    user_id, headers = account(client)
    assert client.patch("/auth/me", headers=headers, json=payload).status_code == 422
    with TestingSessionLocal() as db:
        assert db.get(User, user_id).manager_name_changed_at is None


def test_storage_failure_rolls_back_name_and_timestamp(client, db_session, monkeypatch):
    user_id, _ = account(client)
    user = db_session.get(User, user_id)
    original_commit = db_session.commit
    def fail_commit():
        db_session.flush()
        raise OperationalError("simulated local commit failure", {}, Exception("disk unavailable"))
    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(OperationalError):
        profile_names.update_profile(db_session, user, UserProfileUpdate(first_name="Not Persisted"))
    db_session.rollback()
    monkeypatch.setattr(db_session, "commit", original_commit)
    db_session.refresh(user)
    assert user.first_name == "Old Manager" and user.manager_name_changed_at is None


def test_server_ownership_and_expired_auth(client):
    first_id, first = account(client, "first")
    second_id, _ = account(client, "second")
    assert client.get("/auth/me/name-change-eligibility").status_code == 401
    assert client.patch("/auth/me", headers={"Authorization": "Bearer expired"}, json={"first_name": "Wrong"}).status_code == 401
    wrong = {**first, "X-CFFB-Profile-Account": str(second_id)}
    assert client.patch("/auth/me", headers=wrong, json={"first_name": "Wrong"}).status_code == 409
    valid = client.patch("/auth/me", headers=first, json={"first_name": "First Only", "account_id": second_id})
    assert valid.status_code == 200
    with TestingSessionLocal() as db:
        assert db.get(User, first_id).first_name == "First Only"
        assert db.get(User, second_id).first_name == "Old Manager"


@pytest.mark.parametrize("zone, year, month, day", [("America/New_York", 2026, 3, 7), ("America/New_York", 2026, 10, 31), ("Europe/London", 2026, 3, 28), ("Asia/Tokyo", 2026, 3, 7)])
def test_cooldown_is_elapsed_hours_across_timezones_and_dst(zone, year, month, day):
    last = datetime(year, month, day, 12, tzinfo=ZoneInfo(zone))
    assert next_name_change_at(last) - last.astimezone(timezone.utc) == timedelta(hours=168)


def test_legacy_naive_timestamp_means_utc_not_device_local_time():
    assert next_name_change_at(NOW.replace(tzinfo=None)) == NOW + timedelta(hours=168)


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Row locking must be verified with disposable PostgreSQL")
def test_two_devices_only_commit_one_different_name(client):
    user_id, _ = account(client)
    set_changed(user_id, NOW - timedelta(hours=192))
    barrier = Barrier(2)
    def device(name):
        with TestingSessionLocal() as db:
            user = db.get(User, user_id)  # Deliberately cache both pre-save profiles.
            barrier.wait(timeout=5)
            try:
                saved = profile_names.update_profile(db, user, UserProfileUpdate(first_name=name))
                return "saved", saved.first_name
            except HTTPException as error:
                db.rollback()
                return error.detail["code"], name
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(device, ["Device One", "Device Two"]))
    assert sorted(result[0] for result in results) == ["NAME_CHANGE_COOLDOWN", "saved"]
    winner = next(name for status, name in results if status == "saved")
    with TestingSessionLocal() as db:
        assert db.get(User, user_id).first_name == winner


def test_generated_team_name_collision_does_not_block_manager_name_change(client, db_session):
    from collegefootballfantasy_api.app.models.league import League
    from collegefootballfantasy_api.app.models.team import Team

    user_id, headers = account(client, 'collision')
    other_id, _ = account(client, 'existing-adam')
    leagues = [League(name=f'Name collision {i}', season_year=2026) for i in range(3)]
    db_session.add_all(leagues); db_session.flush()
    own = Team(league_id=leagues[0].id, name="Old Manager's Team", owner_name='Old Manager', owner_user_id=user_id)
    existing = Team(league_id=leagues[0].id, name="Adam's Team", owner_name='Adam', owner_user_id=other_id)
    reserved = Team(league_id=leagues[0].id, name="Adam's Team (2)", owner_user_id=None)
    other_league = Team(league_id=leagues[1].id, name="Old Manager's Team", owner_name='Old Manager', owner_user_id=user_id)
    custom = Team(league_id=leagues[2].id, name='Custom champions', owner_name='Old Manager', owner_user_id=user_id)
    db_session.add_all([own, existing, reserved, other_league, custom]); db_session.commit()
    response = client.patch('/auth/me', headers=headers, json={'first_name': 'Adam'})
    assert response.status_code == 200, response.text
    assert response.json()['first_name'] == 'Adam'
    assert datetime.fromisoformat(response.json()['manager_name_changed_at']) == NOW
    db_session.expire_all()
    assert own.name == "Adam's Team (3)" and own.display_name == "Adam's Team (3)"
    assert existing.name == "Adam's Team" and reserved.name == "Adam's Team (2)"
    assert other_league.name == "Adam's Team"
    assert custom.name == 'Custom champions' and custom.owner_name == 'Adam'
    # An idempotent retry keeps the chosen team name and cooldown unchanged.
    retry = client.patch('/auth/me', headers=headers, json={'first_name': 'Adam'})
    assert retry.status_code == 200
    assert retry.json()['manager_name_changed_at'] == response.json()['manager_name_changed_at']
    assert own.name == "Adam's Team (3)"

    # After the real seven-day window the suffixed generated label follows
    # the next manager name, while custom and opponent labels stay intact.
    set_changed(user_id, NOW - timedelta(hours=192))
    response = client.patch('/auth/me', headers=headers, json={'first_name':'Next Manager'})
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert own.name == "Next Manager's Team"
    assert custom.name == 'Custom champions' and existing.name == "Adam's Team"
