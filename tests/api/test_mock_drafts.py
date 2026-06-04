from datetime import datetime, timedelta, timezone

from api.app.core.config import settings
from api.app.models.draft_pick import DraftPick
from api.app.models.league import League
from api.app.models.league_settings import LeagueSettings
from api.app.models.mock_draft_participant import MockDraftParticipant
from api.app.models.mock_draft_pick import MockDraftPick
from api.app.models.mock_draft_roster import MockDraftRosterEntry
from api.app.models.mock_draft_seat import MockDraftSeat
from api.app.models.mock_draft_session import MockDraftSession
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.services.mock_draft_service import cleanup_expired_mock_drafts


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"mock-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_mock_draft(
    client,
    token: str,
    *,
    team_count: int = 4,
    round_count: int = 3,
    seconds_from_now: int = 60,
    mode: str = "public_multiplayer",
) -> dict:
    response = client.post(
        "/mock-drafts",
        json={
            "name": "Standalone Mock",
            "mode": mode,
            "team_count": team_count,
            "round_count": round_count,
            "pick_timer_seconds": 30,
            "scheduled_start_at": (datetime.now(timezone.utc) + timedelta(seconds=seconds_from_now)).isoformat(),
            "player_pool": "power4",
            "scoring_type": "espn_full_ppr",
            "bot_difficulty": "basic",
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_players(client, total: int) -> list[int]:
    payload = [
        {
            "external_id": None,
            "name": f"Mock Player {index + 1}",
            "position": "QB",
            "school": f"School {index + 1}",
            "image_url": None,
            "sheet_adp": index + 1,
            "sheet_projected_season_points": float(300 - index),
        }
        for index in range(total)
    ]
    response = client.post("/players", json=payload)
    assert response.status_code == 201
    return [row["id"] for row in response.json()]


def create_league(client, token: str) -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Real League Safety Check",
                "season_year": 2026,
                "max_teams": 12,
                "is_private": False,
                "description": "Safety",
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 1},
                "playoff_teams": 4,
                "waiver_type": "faab",
                "trade_review_type": "commissioner",
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


def move_to_intermission(client, db_session, token: str, mock_draft_id: int) -> dict:
    session_row = db_session.get(MockDraftSession, mock_draft_id)
    assert session_row is not None
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    session_row.scheduled_start_at = past
    session_row.draft_datetime_utc = past
    db_session.add(session_row)
    db_session.commit()
    response = client.get(f"/mock-drafts/{mock_draft_id}/room", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def move_to_live(client, db_session, token: str, mock_draft_id: int) -> dict:
    move_to_intermission(client, db_session, token, mock_draft_id)
    session_row = db_session.get(MockDraftSession, mock_draft_id)
    assert session_row is not None
    session_row.intermission_ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(session_row)
    db_session.commit()
    response = client.get(f"/mock-drafts/{mock_draft_id}/room", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_create_mock_draft_requires_auth(client):
    response = client.post(
        "/mock-drafts",
        json={
            "name": "No Auth",
            "team_count": 4,
            "round_count": 13,
            "pick_timer_seconds": 30,
            "scheduled_start_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "player_pool": "power4",
            "scoring_type": "espn_full_ppr",
            "bot_difficulty": "basic",
        },
    )
    assert response.status_code == 401


def test_create_returns_unique_invite_code(client):
    token = create_user_and_token(client, "create")
    first = create_mock_draft(client, token)
    second = create_mock_draft(client, token)

    assert first["mode"] == "public_multiplayer"
    assert len(first["invite_code"]) >= 24
    assert first["invite_code"] != second["invite_code"]
    assert first["invite_link"] == first["join_url"]
    assert first["invite_link"].endswith(f"/draft/mock/invite/{first['invite_code']}")


def test_create_single_player_returns_no_invite_and_starts_live_with_bots(client, db_session):
    token = create_user_and_token(client, "single")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")

    assert created["mode"] == "single_player"
    assert created["invite_code"] is None
    assert created["invite_link"] is None
    assert created["join_url"] is None
    assert created["status"] == "live"

    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None
    assert session_row.mode == "single_player"
    assert session_row.invite_code is None
    assert session_row.current_pick_started_at is not None
    assert session_row.current_pick_expires_at is not None

    room = client.get(f"/mock-drafts/{created['mock_draft_id']}/room", headers=auth_headers(token))
    assert room.status_code == 200, room.text
    payload = room.json()
    assert payload["status"] == "live"
    assert payload["session"]["mode"] == "single_player"
    assert len(payload["participants"]) == 4
    assert len(payload["draft_order"]) == 4
    assert sum(1 for participant in payload["participants"] if participant["participant_type"] == "bot") == 3
    assert db_session.query(RosterEntry).count() == 0
    assert db_session.query(DraftPick).count() == 0
    assert db_session.query(MockDraftRosterEntry).count() == 0
    assert db_session.query(MockDraftSeat).count() == 0


def test_single_player_cannot_be_joined_by_invite(client):
    host_token = create_user_and_token(client, "single-private-host")
    join_token = create_user_and_token(client, "single-private-join")
    created = create_mock_draft(client, host_token, mode="single_player")

    response = client.post(
        "/mock-drafts/join",
        json={"invite_code": created["invite_code"] or "missing-single-player-token"},
        headers=auth_headers(join_token),
    )

    assert response.status_code in {400, 404}


def test_join_requires_account_and_accepts_backend_invite_token(client):
    host_token = create_user_and_token(client, "host")
    join_token = create_user_and_token(client, "join")
    created = create_mock_draft(client, host_token)

    no_auth = client.post("/mock-drafts/join", json={"invite_code": created["invite_code"]})
    assert no_auth.status_code == 401

    joined = client.post(
        "/mock-drafts/join",
        json={"invite_code": created["invite_code"], "team_name": "Joined Team"},
        headers=auth_headers(join_token),
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["joined_count"] == 2

    duplicate = client.post(
        "/mock-drafts/join",
        json={"invite_code": created["invite_code"]},
        headers=auth_headers(join_token),
    )
    assert duplicate.status_code == 409


def test_join_accepts_full_public_invite_link(client):
    host_token = create_user_and_token(client, "link-host")
    join_token = create_user_and_token(client, "link-join")
    created = create_mock_draft(client, host_token)

    joined = client.post(
        "/mock-drafts/join",
        json={"invite_code": created["invite_link"], "team_name": "Public Link Team"},
        headers=auth_headers(join_token),
    )

    assert joined.status_code == 200, joined.text
    assert joined.json()["joined_count"] == 2


def test_join_after_scheduled_lock_fails_and_bots_fill(client, db_session):
    host_token = create_user_and_token(client, "late-host")
    join_token = create_user_and_token(client, "late-join")
    created = create_mock_draft(client, host_token, team_count=4, round_count=1)
    room = move_to_intermission(client, db_session, host_token, created["mock_draft_id"])

    assert room["status"] == "intermission"
    participants = db_session.query(MockDraftParticipant).filter(MockDraftParticipant.mock_draft_id == created["mock_draft_id"]).all()
    assert len(participants) == 4
    assert sum(1 for participant in participants if participant.participant_type == "bot") == 3

    late_join = client.post(
        "/mock-drafts/join",
        json={"invite_code": created["invite_code"]},
        headers=auth_headers(join_token),
    )
    assert late_join.status_code == 409


def test_host_cannot_start_early(client):
    token = create_user_and_token(client, "early")
    created = create_mock_draft(client, token, seconds_from_now=300)

    response = client.post(f"/mock-drafts/{created['mock_draft_id']}/start", headers=auth_headers(token))
    assert response.status_code == 409
    assert "cannot start early" in response.json()["detail"].lower()


def test_draft_order_randomizes_once_and_snake_order_is_correct(client, db_session):
    host_token = create_user_and_token(client, "order-host")
    member_tokens = [create_user_and_token(client, f"order-{index}") for index in range(3)]
    created = create_mock_draft(client, host_token, team_count=4, round_count=2)
    for token in member_tokens:
        join = client.post("/mock-drafts/join", json={"invite_code": created["invite_code"]}, headers=auth_headers(token))
        assert join.status_code == 200, join.text

    first_room = move_to_live(client, db_session, host_token, created["mock_draft_id"])
    first_order = first_room["draft_order"]
    second_room = client.get(f"/mock-drafts/{created['mock_draft_id']}/room", headers=auth_headers(host_token)).json()
    assert second_room["draft_order"] == first_order
    assert sorted(first_order) == sorted(participant["id"] for participant in first_room["participants"])

    round_one = [first_room["participants"][index]["id"] for index in range(4)]
    round_two_pick_one = db_session.query(MockDraftParticipant).filter(MockDraftParticipant.id == round_one[-1]).first()
    assert round_two_pick_one is not None


def test_human_can_pick_only_on_turn_and_real_tables_are_untouched(client, db_session):
    host_token = create_user_and_token(client, "pick-host")
    member_token = create_user_and_token(client, "pick-member")
    league = create_league(client, host_token)
    league_before = db_session.get(League, league["id"]).status
    created = create_mock_draft(client, host_token, team_count=4, round_count=1)
    join = client.post("/mock-drafts/join", json={"invite_code": created["invite_code"]}, headers=auth_headers(member_token))
    assert join.status_code == 200
    player_id = create_players(client, 10)[0]
    room = move_to_live(client, db_session, host_token, created["mock_draft_id"])
    participants = (
        db_session.query(MockDraftParticipant)
        .filter(MockDraftParticipant.mock_draft_id == created["mock_draft_id"])
        .order_by(MockDraftParticipant.is_host.desc(), MockDraftParticipant.id.asc())
        .all()
    )
    for participant in participants:
        participant.draft_position = None
        db_session.add(participant)
    db_session.flush()
    for index, participant in enumerate(participants, start=1):
        participant.draft_position = index
        db_session.add(participant)
    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    session_row.current_overall_pick = 1
    session_row.current_pick_started_at = datetime.now(timezone.utc)
    session_row.current_pick_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    db_session.add(session_row)
    db_session.commit()
    room = client.get(f"/mock-drafts/{created['mock_draft_id']}/room", headers=auth_headers(host_token)).json()
    current_participant = db_session.get(MockDraftParticipant, room["current_participant_id"])
    assert current_participant is not None
    on_clock_token = host_token if current_participant.user_id == db_session.query(MockDraftParticipant).filter_by(mock_draft_id=created["mock_draft_id"], is_host=True).first().user_id else member_token
    off_clock_token = member_token if on_clock_token == host_token else host_token

    off_clock = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/picks",
        json={"player_id": player_id},
        headers=auth_headers(off_clock_token),
    )
    assert off_clock.status_code == 403

    pick = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/picks",
        json={"player_id": player_id},
        headers=auth_headers(on_clock_token),
    )
    assert pick.status_code == 200, pick.text
    assert db_session.query(RosterEntry).count() == 0
    assert db_session.query(DraftPick).count() == 0
    assert db_session.query(MockDraftRosterEntry).count() == 0
    assert db_session.query(MockDraftSeat).count() == 0
    assert db_session.get(League, league["id"]).status == league_before


def test_bot_and_human_timer_auto_pick(client, db_session):
    host_token = create_user_and_token(client, "auto-host")
    created = create_mock_draft(client, host_token, team_count=4, round_count=2)
    create_players(client, 20)
    room = move_to_live(client, db_session, host_token, created["mock_draft_id"])
    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None

    auto = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={"force": True},
        headers=auth_headers(host_token),
    )
    assert auto.status_code == 200, auto.text
    assert len(auto.json()["picks"]) == 1
    first_pick = db_session.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == created["mock_draft_id"]).first()
    assert first_pick.pick_source in {"bot", "auto_timer"}

    participant = db_session.get(MockDraftParticipant, first_pick.participant_id)
    assert participant.auto_pick_count == 1

    duplicate_safe = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={"force": True},
        headers=auth_headers(host_token),
    )
    assert duplicate_safe.status_code == 200
    picks = db_session.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == created["mock_draft_id"]).all()
    assert len({pick.overall_pick for pick in picks}) == len(picks)
    assert len({pick.player_id for pick in picks}) == len(picks)


def test_full_156_pick_mock_draft_simulation_completes_without_real_writes(client, db_session):
    host_token = create_user_and_token(client, "full-host")
    member_tokens = [create_user_and_token(client, f"full-member-{index}") for index in range(3)]
    league = create_league(client, host_token)
    league_before = db_session.get(League, league["id"]).status
    created = create_mock_draft(client, host_token, team_count=12, round_count=13)
    for token in member_tokens:
        response = client.post("/mock-drafts/join", json={"invite_code": created["invite_code"]}, headers=auth_headers(token))
        assert response.status_code == 200, response.text
    create_players(client, 200)
    room = move_to_live(client, db_session, host_token, created["mock_draft_id"])
    assert room["status"] == "live"

    for _index in range(156):
        response = client.post(
            f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
            json={"force": True},
            headers=auth_headers(host_token),
        )
        assert response.status_code == 200, response.text
        room = response.json()
        if room["is_complete"]:
            break

    assert room["is_complete"] is True
    assert room["status"] == "completed"
    assert room["should_show_email_prompt"] is True
    picks = db_session.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == created["mock_draft_id"]).all()
    assert len(picks) == 156
    assert len({pick.overall_pick for pick in picks}) == 156
    assert len({pick.player_id for pick in picks}) == 156
    assert db_session.query(RosterEntry).count() == 0
    assert db_session.query(DraftPick).count() == 0
    assert db_session.query(MockDraftRosterEntry).count() == 0
    assert db_session.query(MockDraftSeat).count() == 0
    assert db_session.get(League, league["id"]).status == league_before

    history = client.get(f"/mock-drafts/{created['mock_draft_id']}/history", headers=auth_headers(host_token))
    assert history.status_code == 200
    assert history.json()["pick_count"] == 156


def test_email_history_fallback_success_and_cleanup(client, db_session):
    host_token = create_user_and_token(client, "email-host")
    created = create_mock_draft(client, host_token, team_count=4, round_count=1)
    create_players(client, 10)
    move_to_live(client, db_session, host_token, created["mock_draft_id"])
    for _index in range(4):
        response = client.post(
            f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
            json={"force": True},
            headers=auth_headers(host_token),
        )
        assert response.status_code == 200

    missing = client.post(f"/mock-drafts/{created['mock_draft_id']}/history/email", headers=auth_headers(host_token))
    assert missing.status_code == 503
    assert missing.json()["detail"]["history"]["pick_count"] == 4

    prior_key = settings.resend_api_key
    settings.resend_api_key = "test-key"
    try:
        sent = client.post(f"/mock-drafts/{created['mock_draft_id']}/history/email", headers=auth_headers(host_token))
    finally:
        settings.resend_api_key = prior_key
    assert sent.status_code == 200, sent.text
    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row.should_preserve_history is True
    assert session_row.history_email_sent_at is not None

    session_row.should_preserve_history = False
    session_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(session_row)
    db_session.commit()
    counts = cleanup_expired_mock_drafts(db_session)
    db_session.commit()
    assert counts["sessions"] == 1
    assert db_session.get(MockDraftSession, created["mock_draft_id"]) is None


def test_exit_live_keeps_human_seat(client, db_session):
    host_token = create_user_and_token(client, "exit-host")
    created = create_mock_draft(client, host_token, team_count=4, round_count=1)
    move_to_live(client, db_session, host_token, created["mock_draft_id"])

    response = client.post(f"/mock-drafts/{created['mock_draft_id']}/exit", headers=auth_headers(host_token))
    assert response.status_code == 200
    assert response.json()["navigate_to"] == "/draft"
    participant = db_session.query(MockDraftParticipant).filter(MockDraftParticipant.mock_draft_id == created["mock_draft_id"], MockDraftParticipant.is_host.is_(True)).first()
    assert participant.participant_type == "human"
    assert participant.connection_status == "disconnected"
