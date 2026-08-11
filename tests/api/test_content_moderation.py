from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.chat import ChatMessage
from collegefootballfantasy_api.app.models.moderation_event import ModerationEvent
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.content_moderation import BLOCKED_MESSAGE, assess_user_text
from conftest import TestingSessionLocal, admin_headers


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, suffix: str) -> tuple[str, int]:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach {suffix}",
            "username": f"manager-{suffix}",
            "email": f"moderation-{suffix}@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"], response.json()["user"]["id"]


def _league_payload(name: str) -> dict:
    return {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": 2,
            "is_private": True,
            "description": "A normal league for football friends.",
            "icon_url": "https://images.example.com/league.png",
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "BENCH": 4, "K": 1, "IR": 1},
            "playoff_teams": 2,
            "waiver_type": "faab",
            "trade_review_type": "none",
            "superflex_enabled": False,
            "kicker_enabled": True,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": "2026-08-19T18:00:00Z",
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }


def _create_league(client, token: str, name: str = "Saturday Banter League") -> dict:
    response = client.post("/leagues", json=_league_payload(name), headers=_headers(token))
    assert response.status_code == 201
    return response.json()["league"]


def _thread_id(client, token: str, league_id: int) -> int:
    response = client.get(f"/leagues/{league_id}/chats", headers=_headers(token))
    assert response.status_code == 200
    return response.json()["data"][0]["id"]


def test_normalization_blocks_leetspeak_without_blocking_fantasy_banter():
    assert assess_user_text("Awful trade, skill issue. You got robbed.").allowed
    assert assess_user_text("spice up the tailgate").allowed
    assert not assess_user_text("f.a.g.g.o.t").allowed
    assert not assess_user_text("F@GG0T").allowed
    assert not assess_user_text("faaaagggot").allowed
    assert not assess_user_text("LLLLLLLLLLLLL").allowed


def test_league_and_profile_names_are_moderated_before_creation(client):
    clean_token, _clean_user_id = _signup(client, "clean")
    clean = client.post("/leagues", json=_league_payload("Normal Football Jokes"), headers=_headers(clean_token))
    assert clean.status_code == 201

    blocked_league = client.post(
        "/leagues", json=_league_payload("F@GG0T League"), headers=_headers(clean_token)
    )
    assert blocked_league.status_code == 422
    assert blocked_league.json()["detail"] == BLOCKED_MESSAGE

    blocked_profile = client.post(
        "/auth/signup",
        json={
            "first_name": "F@GG0T",
            "email": "blocked-profile@example.com",
            "password": "StrongPass123!",
        },
    )
    assert blocked_profile.status_code == 422
    assert blocked_profile.json()["detail"] == BLOCKED_MESSAGE

    unsafe_url_payload = _league_payload("Safe URL Check League")
    unsafe_url_payload["basics"]["icon_url"] = "https://bit.ly/not-a-league-icon"
    unsafe_url = client.post("/leagues", json=unsafe_url_payload, headers=_headers(clean_token))
    assert unsafe_url.status_code == 422
    assert "safe HTTPS link" in unsafe_url.json()["detail"]

    with TestingSessionLocal() as db:
        events = db.query(ModerationEvent).order_by(ModerationEvent.id.asc()).all()
        assert {event.field_name for event in events} >= {"league_name", "manager_name"}
        assert all(event.content_sha256 and len(event.content_sha256) == 64 for event in events)
        assert all("faggot" not in str(event.metadata_json).casefold() for event in events)


def test_league_accepts_a_standard_length_safe_https_image_url(client):
    token, _user_id = _signup(client, "long-league-image")
    image_url = "https://images.example.com/" + ("a" * (2048 - len("https://images.example.com/")))
    assert len(image_url) == 2048
    payload = _league_payload("Long Image URL League")
    payload["basics"]["icon_url"] = image_url

    response = client.post("/leagues", json=payload, headers=_headers(token))

    assert response.status_code == 201
    assert response.json()["league"]["icon_url"] == image_url


def test_chat_blocks_persists_only_clean_messages_and_records_admin_safe_audit(client):
    token, user_id = _signup(client, "chat")
    league = _create_league(client, token)
    thread_id = _thread_id(client, token, league["id"])
    route = f"/leagues/{league['id']}/chats/{thread_id}/messages"

    clean = client.post(
        route,
        json={"body": "Awful trade, skill issue.", "client_message_id": "clean-chat"},
        headers=_headers(token),
    )
    blocked = client.post(
        route,
        json={"body": "f@gg0t", "client_message_id": "blocked-chat"},
        headers=_headers(token),
    )
    duplicate = client.post(
        route,
        json={"body": "Awful trade, skill issue.", "client_message_id": "duplicate-chat"},
        headers=_headers(token),
    )
    blocked_edit = client.patch(
        f"{route}/{clean.json()['id']}",
        json={"body": "f.a.g.g.o.t"},
        headers=_headers(token),
    )

    assert clean.status_code == 201
    assert blocked.status_code == 422
    assert blocked.json()["detail"] == BLOCKED_MESSAGE
    assert duplicate.status_code == 409
    assert blocked_edit.status_code == 422

    with TestingSessionLocal() as db:
        messages = db.query(ChatMessage).filter(ChatMessage.sender_user_id == user_id).all()
        assert len(messages) == 1
        assert messages[0].body == "Awful trade, skill issue."
        events = db.query(ModerationEvent).filter(ModerationEvent.actor_user_id == user_id).all()
        assert {event.reason_code for event in events} >= {"hate", "spam_duplicate_message"}
        assert all(event.content_sha256 and len(event.content_sha256) == 64 for event in events)

        user = db.get(User, user_id)
        assert user is not None
        user.is_admin = True
        db.commit()

    admin = client.get("/admin/moderation/events", headers=_headers(token))
    assert admin.status_code == 200
    assert {row["reason_code"] for row in admin.json()["data"]} >= {"hate", "spam_duplicate_message"}
    assert all("content_sha256" not in row for row in admin.json()["data"])


def test_chat_flood_protection_is_logged(client, monkeypatch):
    token, _user_id = _signup(client, "flood")
    league = _create_league(client, token, "Flood Control League")
    thread_id = _thread_id(client, token, league["id"])
    route = f"/leagues/{league['id']}/chats/{thread_id}/messages"
    monkeypatch.setattr(settings, "chat_message_rate_limit", 1)
    monkeypatch.setattr(settings, "chat_message_sustained_rate_limit", 100)

    first = client.post(route, json={"body": "First message", "client_message_id": "flood-first"}, headers=_headers(token))
    blocked = client.post(route, json={"body": "Second message", "client_message_id": "flood-second"}, headers=_headers(token))

    assert first.status_code == 201
    assert blocked.status_code == 429
    with TestingSessionLocal() as db:
        assert db.query(ModerationEvent).filter(ModerationEvent.reason_code == "spam_flood_protection").count() == 1
