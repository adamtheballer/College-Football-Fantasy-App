from datetime import datetime, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.models.audit_event import AuditEvent
from collegefootballfantasy_api.app.models.league_message import LeagueMessage, LeagueMessageRead, LeagueMessageReport
from collegefootballfantasy_api.app.models.user import User


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user(client, suffix: str) -> dict:
    response = client.post(
        "/auth/signup",
        json={"first_name": f"Chat{suffix}", "email": f"chat-{suffix}@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 201
    payload = response.json()
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == f"chat-{suffix}@example.com").one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return {"user": payload["user"], "access_token": payload["access_token"]}


def create_league(client, token: str, name: str = "Chat League") -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": name,
                "season_year": 2026,
                "max_teams": 4,
                "is_private": True,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "BENCH": 2},
                "playoff_teams": 2,
                "waiver_type": "faab",
                "trade_review_type": "commissioner",
                "superflex_enabled": False,
                "kicker_enabled": True,
                "defense_enabled": False,
            },
            "draft": {
                "draft_datetime_utc": "2026-08-19T18:00:00Z",
                "timezone": "America/Los_Angeles",
                "draft_type": "snake",
                "pick_timer_seconds": 90,
            },
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def test_league_chat_requires_membership_and_posts_messages(client):
    owner = create_user(client, "owner")
    outsider = create_user(client, "outsider")
    league = create_league(client, owner["access_token"])

    forbidden = client.get(f"/leagues/{league['id']}/chat/messages", headers=auth_headers(outsider["access_token"]))
    assert forbidden.status_code == 403

    post_response = client.post(
        f"/leagues/{league['id']}/chat/messages",
        json={"body": "Draft room is open.", "message_type": "user"},
        headers=auth_headers(owner["access_token"]),
    )
    assert post_response.status_code == 201
    message = post_response.json()
    assert message["body"] == "Draft room is open."
    assert message["can_edit"] is True
    assert message["can_delete"] is True

    list_response = client.get(f"/leagues/{league['id']}/chat/messages", headers=auth_headers(owner["access_token"]))
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["data"][0]["id"] == message["id"]


def test_league_chat_unread_cursor_and_pagination(client):
    owner = create_user(client, "reader-owner")
    member = create_user(client, "reader-member")
    league = create_league(client, owner["access_token"], "Reader League")
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member["access_token"])).status_code == 200

    ids: list[int] = []
    for index in range(3):
        response = client.post(
            f"/leagues/{league['id']}/chat/messages",
            json={"body": f"Message {index}", "message_type": "user"},
            headers=auth_headers(owner["access_token"]),
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])

    unread = client.get(f"/leagues/{league['id']}/chat/messages", headers=auth_headers(member["access_token"]))
    assert unread.status_code == 200
    assert unread.json()["unread_count"] == 3

    read_response = client.post(
        f"/leagues/{league['id']}/chat/read",
        json={"last_read_message_id": ids[1]},
        headers=auth_headers(member["access_token"]),
    )
    assert read_response.status_code == 200
    assert read_response.json()["unread_count"] == 1

    after_response = client.get(
        f"/leagues/{league['id']}/chat/messages",
        params={"after_id": ids[1]},
        headers=auth_headers(member["access_token"]),
    )
    assert after_response.status_code == 200
    assert [row["id"] for row in after_response.json()["data"]] == [ids[2]]


def test_league_chat_edit_delete_report_and_audit(client, db_session):
    owner = create_user(client, "edit-owner")
    member = create_user(client, "edit-member")
    league = create_league(client, owner["access_token"], "Edit League")
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member["access_token"])).status_code == 200

    message_response = client.post(
        f"/leagues/{league['id']}/chat/messages",
        json={"body": "Original message", "message_type": "user"},
        headers=auth_headers(owner["access_token"]),
    )
    message_id = message_response.json()["id"]

    member_edit = client.patch(
        f"/leagues/{league['id']}/chat/messages/{message_id}",
        json={"body": "bad edit"},
        headers=auth_headers(member["access_token"]),
    )
    assert member_edit.status_code == 403

    owner_edit = client.patch(
        f"/leagues/{league['id']}/chat/messages/{message_id}",
        json={"body": "Edited message"},
        headers=auth_headers(owner["access_token"]),
    )
    assert owner_edit.status_code == 200
    assert owner_edit.json()["body"] == "Edited message"
    assert owner_edit.json()["edited_at"] is not None

    report = client.post(
        f"/leagues/{league['id']}/chat/messages/{message_id}/report",
        json={"reason": "This is spam"},
        headers=auth_headers(member["access_token"]),
    )
    assert report.status_code == 201
    duplicate_report = client.post(
        f"/leagues/{league['id']}/chat/messages/{message_id}/report",
        json={"reason": "This is still spam"},
        headers=auth_headers(member["access_token"]),
    )
    assert duplicate_report.status_code == 409

    delete_response = client.delete(
        f"/leagues/{league['id']}/chat/messages/{message_id}",
        headers=auth_headers(member["access_token"]),
    )
    assert delete_response.status_code == 403
    commissioner_delete = client.delete(
        f"/leagues/{league['id']}/chat/messages/{message_id}",
        headers=auth_headers(owner["access_token"]),
    )
    assert commissioner_delete.status_code == 200
    assert commissioner_delete.json()["body"] == "[deleted]"
    assert commissioner_delete.json()["deleted_at"] is not None

    db_session.expire_all()
    assert db_session.query(LeagueMessageReport).count() == 1
    assert db_session.query(AuditEvent).filter(AuditEvent.action.in_(["league.chat.message.create", "league.chat.message.edit", "league.chat.message.delete", "league.chat.message.report"])).count() >= 4


def test_league_chat_spam_guard_rate_limit_and_system_messages(client, db_session):
    owner = create_user(client, "guard-owner")
    member = create_user(client, "guard-member")
    league = create_league(client, owner["access_token"], "Guard League")
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member["access_token"])).status_code == 200

    system_denied = client.post(
        f"/leagues/{league['id']}/chat/messages",
        json={"body": "System update", "message_type": "system"},
        headers=auth_headers(member["access_token"]),
    )
    assert system_denied.status_code == 403

    system_allowed = client.post(
        f"/leagues/{league['id']}/chat/messages",
        json={"body": "Commissioner update", "message_type": "commissioner"},
        headers=auth_headers(owner["access_token"]),
    )
    assert system_allowed.status_code == 201
    assert system_allowed.json()["message_type"] == "commissioner"

    spam_response = client.post(
        f"/leagues/{league['id']}/chat/messages",
        json={"body": "free money crypto pump", "message_type": "user"},
        headers=auth_headers(member["access_token"]),
    )
    assert spam_response.status_code == 400

    for index in range(8):
        response = client.post(
            f"/leagues/{league['id']}/chat/messages",
            json={"body": f"Rapid message {index}", "message_type": "user"},
            headers=auth_headers(member["access_token"]),
        )
        assert response.status_code == 201
    limited = client.post(
        f"/leagues/{league['id']}/chat/messages",
        json={"body": "Too many messages", "message_type": "user"},
        headers=auth_headers(member["access_token"]),
    )
    assert limited.status_code == 429

    db_session.expire_all()
    assert db_session.query(LeagueMessage).filter(LeagueMessage.league_id == league["id"]).count() == 9
    assert db_session.query(LeagueMessageRead).filter(LeagueMessageRead.league_id == league["id"]).count() == 0
