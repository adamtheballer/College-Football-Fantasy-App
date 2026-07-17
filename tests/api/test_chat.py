import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collegefootballfantasy_api.app.models.chat import ChatAuditEvent, ChatMessage, ChatReadState, ChatThread, ChatThreadParticipant
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from conftest import TestingSessionLocal


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user(client, suffix: str) -> tuple[str, int]:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach {suffix}",
            "email": f"chat-{suffix}@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"], response.json()["user"]["id"]


def create_league(client, token: str, *, max_teams: int = 2) -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Chat Test League",
                "season_year": 2026,
                "max_teams": max_teams,
                "is_private": True,
                "description": None,
                "icon_url": None,
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
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def join_league(client, token: str, league_id: int) -> None:
    response = client.post(f"/leagues/{league_id}/join", headers=auth_headers(token))
    assert response.status_code == 200


def _load_chat_migration():
    migration_path = Path(__file__).resolve().parents[2] / "api" / "alembic" / "versions" / "0037_league_chat_threads.py"
    spec = importlib.util.spec_from_file_location("league_chat_threads_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_chat_security_migration():
    migration_path = Path(__file__).resolve().parents[2] / "api" / "alembic" / "versions" / "0038_chat_security_audits.py"
    spec = importlib.util.spec_from_file_location("chat_security_audits_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_chat_migration_preserves_legacy_message_types_and_revision_chain():
    migration = _load_chat_migration()

    assert migration.down_revision == "0036_worker_health"
    assert migration._mapped_legacy_message_type("system") == "system"
    assert migration._mapped_legacy_message_type("trade") == "trade_processed"
    assert migration._mapped_legacy_message_type("unrecognized") == "system"
    source = Path(migration.__file__).read_text()
    assert "FROM league_messages" in source
    assert "legacy_league_message_id" in source
    assert "drop_table(\"league_messages\")" not in source


def test_chat_security_audit_migration_tracks_member_removals():
    migration = _load_chat_security_migration()

    assert migration.down_revision == "0037_league_chat_threads"
    source = Path(migration.__file__).read_text()
    assert "chat_audit_events" in source
    assert "league_member_removed" in source
    assert "trg_league_members_chat_removal_audit" in source


def test_chat_query_index_migration_matches_unread_access_paths():
    migration_path = Path(__file__).resolve().parents[2] / "api" / "alembic" / "versions" / "0039_chat_query_indexes.py"
    source = migration_path.read_text()
    expected_indexes = {
        "ix_chat_threads_league_type",
        "ix_chat_thread_participants_user_thread",
        "ix_chat_messages_thread_id",
        "ix_chat_messages_sender_user_id",
    }

    assert "ix_chat_threads_league_type" in {index.name for index in ChatThread.__table__.indexes}
    assert "ix_chat_thread_participants_user_thread" in {index.name for index in ChatThreadParticipant.__table__.indexes}
    assert {"ix_chat_messages_thread_id", "ix_chat_messages_sender_user_id"}.issubset(
        {index.name for index in ChatMessage.__table__.indexes}
    )
    assert any(
        constraint.name == "uq_chat_read_states_thread_user"
        for constraint in ChatReadState.__table__.constraints
    )
    assert all(index_name in source for index_name in expected_indexes)
    assert "down_revision" in source and "0038_chat_security_audits" in source


def test_league_chat_creates_one_master_thread_and_blocks_non_members(client):
    owner_token, _owner_id = create_user(client, "owner")
    member_token, member_id = create_user(client, "member")
    guest_token, _guest_id = create_user(client, "guest")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])

    first = client.get(f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token))
    second = client.get(f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token))
    blocked = client.get(f"/leagues/{league['id']}/chats", headers=auth_headers(guest_token))

    assert first.status_code == 200
    assert second.status_code == 200
    assert [thread["thread_type"] for thread in first.json()["data"]] == ["league"]
    assert first.json()["data"][0]["id"] == second.json()["data"][0]["id"]
    assert first.json()["data"][0]["title"] == "General"
    assert member_id in {participant["user_id"] for participant in first.json()["data"][0]["participants"]}
    assert all("display_name" in participant and "fantasy_team_name" in participant for participant in first.json()["data"][0]["participants"])
    assert blocked.status_code == 403


def test_direct_threads_are_scoped_to_the_league_and_deduplicated(client):
    owner_token, owner_id = create_user(client, "direct-owner")
    member_token, member_id = create_user(client, "direct-member")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])

    first = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": member_id},
        headers=auth_headers(owner_token),
    )
    second = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": owner_id},
        headers=auth_headers(member_token),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["thread_type"] == "direct"
    assert {participant["user_id"] for participant in first.json()["participants"]} == {owner_id, member_id}
    assert {participant["display_name"] for participant in first.json()["participants"]} == {
        "Coach direct-owner",
        "Coach direct-member",
    }
    assert all("fantasy_team_name" in participant for participant in first.json()["participants"])
    direct_from_list = next(
        thread
        for thread in client.get(f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)).json()["data"]
        if thread["id"] == first.json()["id"]
    )
    assert direct_from_list["other_participant"]["user_id"] == member_id
    assert direct_from_list["other_participant"]["display_name"] == "Coach direct-member"


def test_same_direct_pair_can_have_distinct_threads_in_different_leagues(client):
    owner_token, _owner_id = create_user(client, "pair-owner")
    member_token, member_id = create_user(client, "pair-member")
    first_league = create_league(client, owner_token)
    second_league = create_league(client, owner_token)
    join_league(client, member_token, first_league["id"])
    join_league(client, member_token, second_league["id"])

    first = client.post(
        f"/leagues/{first_league['id']}/chats/direct",
        json={"recipient_user_id": member_id},
        headers=auth_headers(owner_token),
    )
    second = client.post(
        f"/leagues/{second_league['id']}/chats/direct",
        json={"recipient_user_id": member_id},
        headers=auth_headers(owner_token),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["league_id"] != second.json()["league_id"]


def test_direct_messages_reject_self_non_members_and_outside_access(client):
    owner_token, owner_id = create_user(client, "dm-owner")
    member_token, member_id = create_user(client, "dm-member")
    third_member_token, _third_member_id = create_user(client, "dm-third-member")
    _non_member_token, non_member_id = create_user(client, "dm-non-member")
    league = create_league(client, owner_token, max_teams=4)
    join_league(client, member_token, league["id"])
    join_league(client, third_member_token, league["id"])

    self_message = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": owner_id},
        headers=auth_headers(owner_token),
    )
    non_member_recipient = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": non_member_id},
        headers=auth_headers(owner_token),
    )
    direct = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": member_id},
        headers=auth_headers(owner_token),
    )
    outside_access = client.get(
        f"/leagues/{league['id']}/chats/{direct.json()['id']}/messages",
        headers=auth_headers(third_member_token),
    )

    assert self_message.status_code == 422
    assert non_member_recipient.status_code == 403
    assert direct.status_code == 201
    assert outside_access.status_code == 404


def test_messages_are_idempotent_and_read_cursor_clears_unread_count(client):
    owner_token, _owner_id = create_user(client, "message-owner")
    member_token, _member_id = create_user(client, "message-member")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])
    threads = client.get(f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)).json()["data"]
    master_thread_id = next(thread["id"] for thread in threads if thread["thread_type"] == "league")

    first = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/messages",
        json={"body": "Ready for the draft?", "client_message_id": "browser-send-1"},
        headers=auth_headers(owner_token),
    )
    duplicate = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/messages",
        json={"body": "Ready for the draft?", "client_message_id": "browser-send-1"},
        headers=auth_headers(owner_token),
    )
    unread = client.get("/chats/unread-summary", headers=auth_headers(member_token))
    read = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/read",
        json={"last_read_message_id": first.json()["id"]},
        headers=auth_headers(member_token),
    )
    unread_after = client.get("/chats/unread-summary", headers=auth_headers(member_token))

    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == first.json()["id"]
    assert first.json()["sender_display_name"] == "Coach message-owner"
    assert first.json()["metadata"] == {}
    assert unread.status_code == 200
    assert unread.json()["total_unread"] == 1
    assert read.status_code == 200
    assert read.json()["unread_count"] == 0
    assert read.json()["total_unread"] == 0
    assert unread_after.json()["total_unread"] == 0

    with TestingSessionLocal() as session:
        assert (
            session.query(ChatMessage)
            .filter(ChatMessage.thread_id == master_thread_id, ChatMessage.message_type == "user")
            .count()
            == 1
        )


def test_master_chat_read_and_message_validation_for_active_members(client):
    owner_token, _owner_id = create_user(client, "master-read-owner")
    member_token, _member_id = create_user(client, "master-read-member")
    guest_token, _guest_id = create_user(client, "master-read-guest")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])
    thread_id = client.get(
        f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)
    ).json()["data"][0]["id"]

    member_read = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        headers=auth_headers(member_token),
    )
    nonmember_read = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        headers=auth_headers(guest_token),
    )
    empty_body = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "   "},
        headers=auth_headers(owner_token),
    )
    oversized_body = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "x" * 2001},
        headers=auth_headers(owner_token),
    )

    assert member_read.status_code == 200
    assert nonmember_read.status_code == 403
    assert empty_body.status_code == 422
    assert oversized_body.status_code == 422


def test_mark_read_is_monotonic_and_unread_summary_aggregates_leagues(client):
    owner_token, _owner_id = create_user(client, "read-owner")
    member_token, _member_id = create_user(client, "read-member")
    first_league = create_league(client, owner_token)
    second_league = create_league(client, owner_token)
    join_league(client, member_token, first_league["id"])
    join_league(client, member_token, second_league["id"])

    first_thread_id = client.get(
        f"/leagues/{first_league['id']}/chats", headers=auth_headers(owner_token)
    ).json()["data"][0]["id"]
    second_thread_id = client.get(
        f"/leagues/{second_league['id']}/chats", headers=auth_headers(owner_token)
    ).json()["data"][0]["id"]
    first_message = client.post(
        f"/leagues/{first_league['id']}/chats/{first_thread_id}/messages",
        json={"body": "First", "client_message_id": "read-first"},
        headers=auth_headers(owner_token),
    ).json()
    second_message = client.post(
        f"/leagues/{first_league['id']}/chats/{first_thread_id}/messages",
        json={"body": "Second", "client_message_id": "read-second"},
        headers=auth_headers(owner_token),
    ).json()
    other_league_message = client.post(
        f"/leagues/{second_league['id']}/chats/{second_thread_id}/messages",
        json={"body": "Other league", "client_message_id": "read-other"},
        headers=auth_headers(owner_token),
    )
    mark_latest = client.post(
        f"/leagues/{first_league['id']}/chats/{first_thread_id}/read",
        json={"last_read_message_id": second_message["id"]},
        headers=auth_headers(member_token),
    )
    move_backward = client.post(
        f"/leagues/{first_league['id']}/chats/{first_thread_id}/read",
        json={"last_read_message_id": first_message["id"]},
        headers=auth_headers(member_token),
    )
    summary = client.get("/chats/unread-summary", headers=auth_headers(member_token))

    assert other_league_message.status_code == 201
    assert mark_latest.status_code == 200
    assert move_backward.status_code == 409
    assert summary.status_code == 200
    assert summary.json() == {
        "total_unread": 1,
        "leagues": [{"league_id": second_league["id"], "unread": 1}],
    }


def test_master_chat_helper_reuses_an_existing_thread(client, db_session):
    from collegefootballfantasy_api.app.services.chat_service import get_or_create_league_chat_thread

    owner_token, _owner_id = create_user(client, "master-helper")
    league = create_league(client, owner_token)

    first = get_or_create_league_chat_thread(db_session, league["id"])
    db_session.commit()
    second = get_or_create_league_chat_thread(db_session, league["id"])

    assert first.id == second.id
    assert db_session.query(ChatThread).filter(
        ChatThread.league_id == league["id"], ChatThread.thread_type == "league"
    ).count() == 1


def test_plain_text_and_cross_thread_replies_are_enforced(client):
    owner_token, _owner_id = create_user(client, "reply-owner")
    member_token, member_id = create_user(client, "reply-member")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])
    threads = client.get(f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)).json()["data"]
    master_thread_id = threads[0]["id"]
    direct = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": member_id},
        headers=auth_headers(owner_token),
    ).json()
    master_message = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/messages",
        json={"body": "Master message"},
        headers=auth_headers(owner_token),
    ).json()

    markup = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/messages",
        json={"body": "<b>not plain text</b>"},
        headers=auth_headers(owner_token),
    )
    control_characters = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/messages",
        json={"body": "Bad\u0000message"},
        headers=auth_headers(owner_token),
    )
    cross_thread_reply = client.post(
        f"/leagues/{league['id']}/chats/{direct['id']}/messages",
        json={"body": "Wrong reply target", "reply_to_message_id": master_message["id"]},
        headers=auth_headers(owner_token),
    )

    assert markup.status_code == 422
    assert control_characters.status_code == 422
    assert cross_thread_reply.status_code == 422


def test_system_event_key_prevents_duplicate_finalized_trade_announcements(client, db_session):
    from collegefootballfantasy_api.app.models.chat import ChatThread
    from collegefootballfantasy_api.app.services.chat_service import create_system_chat_message

    owner_token, _owner_id = create_user(client, "system")
    league = create_league(client, owner_token)

    first = create_system_chat_message(
        db_session,
        league_id=league["id"],
        message_type="trade_finalized",
        body="Trade finalized",
        event_key="trade:99:finalized",
    )
    second = create_system_chat_message(
        db_session,
        league_id=league["id"],
        message_type="trade_finalized",
        body="Trade finalized",
        event_key="trade:99:finalized",
    )
    db_session.commit()

    assert first.id == second.id
    assert db_session.query(ChatThread).filter(ChatThread.league_id == league["id"]).count() == 1
    assert db_session.query(ChatMessage).filter(ChatMessage.event_key == "trade:99:finalized").count() == 1


def test_system_messages_count_as_unread_for_other_league_members(client, db_session):
    from collegefootballfantasy_api.app.services.chat_service import create_system_chat_message

    owner_token, _owner_id = create_user(client, "system-unread-owner")
    member_token, _member_id = create_user(client, "system-unread-member")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])
    create_system_chat_message(
        db_session,
        league_id=league["id"],
        message_type="trade_finalized",
        body="Trade finalized",
        event_key="trade:system-unread:finalized",
    )
    db_session.commit()

    unread = client.get("/chats/unread-summary", headers=auth_headers(member_token))

    assert unread.status_code == 200
    assert unread.json()["total_unread"] == 1
    assert unread.json()["leagues"] == [{"league_id": league["id"], "unread": 1}]


def test_removed_member_loses_chat_access_immediately(client, db_session):
    owner_token, _owner_id = create_user(client, "removed-owner")
    member_token, member_id = create_user(client, "removed-member")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])
    thread_id = client.get(
        f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)
    ).json()["data"][0]["id"]
    membership = (
        db_session.query(LeagueMember)
        .filter(LeagueMember.league_id == league["id"], LeagueMember.user_id == member_id)
        .one()
    )
    db_session.delete(membership)
    db_session.commit()

    response = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        headers=auth_headers(member_token),
    )

    assert response.status_code == 403


def test_message_pagination_and_rate_limit(client, monkeypatch):
    from collegefootballfantasy_api.app.core.config import settings

    owner_token, _owner_id = create_user(client, "page-owner")
    league = create_league(client, owner_token)
    thread_id = client.get(
        f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)
    ).json()["data"][0]["id"]
    for index in range(3):
        response = client.post(
            f"/leagues/{league['id']}/chats/{thread_id}/messages",
            json={"body": f"Message {index}", "client_message_id": f"page-{index}"},
            headers=auth_headers(owner_token),
        )
        assert response.status_code == 201

    first_page = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages?limit=2",
        headers=auth_headers(owner_token),
    )
    second_page = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages?limit=2&before_message_id={first_page.json()['next_before_message_id']}",
        headers=auth_headers(owner_token),
    )
    after_page = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages?limit=2&after_message_id={first_page.json()['data'][0]['id']}",
        headers=auth_headers(owner_token),
    )
    conflicting_cursors = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages?before_message_id=2&after_message_id=1",
        headers=auth_headers(owner_token),
    )
    assert first_page.status_code == 200
    assert len(first_page.json()["data"]) == 2
    assert first_page.json()["next_before_message_id"] is not None
    assert second_page.status_code == 200
    assert len(second_page.json()["data"]) == 1
    assert after_page.status_code == 200
    assert [message["body"] for message in after_page.json()["data"]] == ["Message 2"]
    assert conflicting_cursors.status_code == 422

    monkeypatch.setattr(settings, "chat_message_rate_limit", 1)
    limited = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "Rate-limited message", "client_message_id": "rate-limited"},
        headers=auth_headers(owner_token),
    )

    assert limited.status_code == 429


def test_incremental_cursor_zero_and_chat_rate_windows(client, monkeypatch):
    from collegefootballfantasy_api.app.core.config import settings

    owner_token, _owner_id = create_user(client, "rate-owner")
    member_token, member_id = create_user(client, "rate-member")
    extra_member_token, extra_member_id = create_user(client, "rate-extra")
    league = create_league(client, owner_token, max_teams=4)
    join_league(client, member_token, league["id"])
    join_league(client, extra_member_token, league["id"])
    thread_id = client.get(
        f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)
    ).json()["data"][0]["id"]

    incremental = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages?after_message_id=0",
        headers=auth_headers(owner_token),
    )
    assert incremental.status_code == 200

    monkeypatch.setattr(settings, "chat_message_rate_limit", 100)
    monkeypatch.setattr(settings, "chat_message_sustained_rate_limit", 1)
    first_message = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "First", "client_message_id": "sustained-first"},
        headers=auth_headers(owner_token),
    )
    limited_message = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "Second", "client_message_id": "sustained-second"},
        headers=auth_headers(owner_token),
    )

    assert first_message.status_code == 201
    assert limited_message.status_code == 429
    assert "Too many chat requests" in limited_message.json()["detail"]

    other_manager_message = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "Separate manager budget", "client_message_id": "other-manager-budget"},
        headers=auth_headers(member_token),
    )
    assert other_manager_message.status_code == 201

    monkeypatch.setattr(settings, "chat_direct_thread_rate_limit", 1)
    first_direct = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": member_id},
        headers=auth_headers(owner_token),
    )
    limited_direct = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": extra_member_id},
        headers=auth_headers(owner_token),
    )

    assert first_direct.status_code == 201
    assert limited_direct.status_code == 429

    monkeypatch.setattr(settings, "chat_read_rate_limit", 1)
    first_read = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/read",
        json={},
        headers=auth_headers(member_token),
    )
    limited_read = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/read",
        json={},
        headers=auth_headers(member_token),
    )

    assert first_read.status_code == 200
    assert limited_read.status_code == 429


def test_messages_can_be_edited_and_soft_deleted_with_audit(client, db_session):
    owner_token, _owner_id = create_user(client, "moderator-owner")
    member_token, _member_id = create_user(client, "moderator-member")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])
    thread_id = client.get(
        f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)
    ).json()["data"][0]["id"]

    member_message = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "Initial message", "client_message_id": "moderation-message"},
        headers=auth_headers(member_token),
    ).json()
    edited = client.patch(
        f"/leagues/{league['id']}/chats/{thread_id}/messages/{member_message['id']}",
        json={"body": "Updated message"},
        headers=auth_headers(member_token),
    )
    db_session.query(ChatMessage).filter(ChatMessage.id == member_message["id"]).update(
        {"created_at": datetime.now(timezone.utc) - timedelta(minutes=16)}
    )
    db_session.commit()
    expired_edit = client.patch(
        f"/leagues/{league['id']}/chats/{thread_id}/messages/{member_message['id']}",
        json={"body": "Too late"},
        headers=auth_headers(member_token),
    )
    deleted = client.delete(
        f"/leagues/{league['id']}/chats/{thread_id}/messages/{member_message['id']}",
        headers=auth_headers(owner_token),
    )
    self_deleted_message = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "My own deletion", "client_message_id": "self-deletion"},
        headers=auth_headers(member_token),
    ).json()
    self_deleted = client.delete(
        f"/leagues/{league['id']}/chats/{thread_id}/messages/{self_deleted_message['id']}",
        headers=auth_headers(member_token),
    )
    listed = client.get(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        headers=auth_headers(member_token),
    )
    system_message = client.post(
        f"/leagues/{league['id']}/chats/{thread_id}/messages",
        json={"body": "Cannot delete this", "client_message_id": "temporary-owner-message"},
        headers=auth_headers(owner_token),
    )
    with db_session.begin_nested():
        system_message_id = system_message.json()["id"]
        db_session.query(ChatMessage).filter(ChatMessage.id == system_message_id).update({"message_type": "system"})
    db_session.commit()
    forbidden_system_delete = client.delete(
        f"/leagues/{league['id']}/chats/{thread_id}/messages/{system_message_id}",
        headers=auth_headers(owner_token),
    )

    assert edited.status_code == 200
    assert edited.json()["body"] == "Updated message"
    assert edited.json()["edited_at"] is not None
    assert expired_edit.status_code == 409
    assert deleted.status_code == 200
    assert deleted.json()["body"] is None
    assert deleted.json()["deleted_at"] is not None
    assert listed.status_code == 200
    assert next(message for message in listed.json()["data"] if message["id"] == member_message["id"])["body"] is None
    assert forbidden_system_delete.status_code == 403
    assert self_deleted.status_code == 200
    assert self_deleted.json()["body"] is None
    audit = (
        db_session.query(ChatAuditEvent)
        .filter(
            ChatAuditEvent.message_id == member_message["id"],
            ChatAuditEvent.action == "message_deleted_by_commissioner",
        )
        .one()
    )
    assert audit.league_id == league["id"]
    assert (
        db_session.query(ChatAuditEvent)
        .filter(
            ChatAuditEvent.message_id == self_deleted_message["id"],
            ChatAuditEvent.action == "message_deleted_by_sender",
        )
        .count()
        == 1
    )


def test_direct_thread_creation_is_audited(client, db_session):
    owner_token, _owner_id = create_user(client, "audit-owner")
    member_token, member_id = create_user(client, "audit-member")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])

    direct = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": member_id},
        headers=auth_headers(owner_token),
    )

    assert direct.status_code == 201
    audit = (
        db_session.query(ChatAuditEvent)
        .filter(
            ChatAuditEvent.thread_id == direct.json()["id"],
            ChatAuditEvent.action == "direct_thread_created",
        )
        .one()
    )
    assert audit.metadata_json == {"recipient_user_id": member_id}


def test_thread_preview_and_read_cursor_cannot_move_backward(client):
    owner_token, _owner_id = create_user(client, "receipt-owner")
    member_token, _member_id = create_user(client, "receipt-member")
    league = create_league(client, owner_token)
    join_league(client, member_token, league["id"])
    master_thread_id = client.get(
        f"/leagues/{league['id']}/chats", headers=auth_headers(owner_token)
    ).json()["data"][0]["id"]
    first = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/messages",
        json={"body": "First message", "client_message_id": "receipt-first"},
        headers=auth_headers(owner_token),
    ).json()
    second = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/messages",
        json={"body": "Second message", "client_message_id": "receipt-second"},
        headers=auth_headers(owner_token),
    ).json()
    threads = client.get(f"/leagues/{league['id']}/chats", headers=auth_headers(member_token))
    read_latest = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/read",
        json={"last_read_message_id": second["id"]},
        headers=auth_headers(member_token),
    )
    move_backward = client.post(
        f"/leagues/{league['id']}/chats/{master_thread_id}/read",
        json={"last_read_message_id": first["id"]},
        headers=auth_headers(member_token),
    )

    assert threads.status_code == 200
    assert threads.json()["data"][0]["last_message_preview"] == "Second message"
    assert threads.json()["data"][0]["last_message_at"] is not None
    assert read_latest.status_code == 200
    assert move_backward.status_code == 409
