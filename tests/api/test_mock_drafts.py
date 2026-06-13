from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

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
from api.app.services import mock_draft_service


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
    position_cycle = ["QB", "RB", "RB", "WR", "WR", "TE", "K", "RB", "WR", "TE"]
    payload = [
        {
            "external_id": None,
            "name": f"Mock Player {index + 1}",
            "position": position_cycle[index % len(position_cycle)],
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


def test_create_single_player_returns_no_invite_and_enters_pre_draft_countdown_with_bots(client, db_session):
    token = create_user_and_token(client, "single")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")

    assert created["mode"] == "single_player"
    assert created["invite_code"] is None
    assert created["invite_link"] is None
    assert created["join_url"] is None
    assert created["status"] == "intermission"

    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None
    assert session_row.mode == "single_player"
    assert session_row.invite_code is None
    assert session_row.intermission_started_at is not None
    assert session_row.intermission_ends_at is not None
    assert 85 <= (session_row.intermission_ends_at - session_row.intermission_started_at).total_seconds() <= 95
    assert session_row.current_pick_started_at is None
    assert session_row.current_pick_expires_at is None

    room = client.get(f"/mock-drafts/{created['mock_draft_id']}/room", headers=auth_headers(token))
    assert room.status_code == 200, room.text
    payload = room.json()
    assert payload["status"] == "intermission"
    assert payload["phase_type"] == "prestart_countdown"
    assert 0 < payload["seconds_remaining"] <= 90
    assert payload["session"]["mode"] == "single_player"
    assert len(payload["participants"]) == 4
    assert len(payload["draft_order"]) == 4
    assert sum(1 for participant in payload["participants"] if participant["participant_type"] == "bot") == 3
    assert db_session.query(RosterEntry).count() == 0
    assert db_session.query(DraftPick).count() == 0
    assert db_session.query(MockDraftRosterEntry).count() == 0
    assert db_session.query(MockDraftSeat).count() == 0


def test_single_player_pre_draft_countdown_transitions_to_live_and_starts_pick_timer(client, db_session):
    token = create_user_and_token(client, "single-start")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None
    session_row.intermission_ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(session_row)
    db_session.commit()

    room = client.get(f"/mock-drafts/{created['mock_draft_id']}/room", headers=auth_headers(token))
    assert room.status_code == 200, room.text
    payload = room.json()

    assert payload["status"] == "live"
    assert payload["phase_type"] == "pick_clock"
    assert payload["current_pick_started_at"] is not None
    assert payload["current_pick_expires_at"] is not None


def test_available_mock_players_dedupes_canonical_player_rows(client):
    token = create_user_and_token(client, "dedupe-pool")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": "Arch Manning",
                "position": "QB",
                "school": "Texas",
                "image_url": None,
                "sheet_adp": None,
                "sheet_projected_season_points": None,
            },
            {
                "external_id": None,
                "name": "Arch Manning",
                "position": "QB",
                "school": "TEXAS",
                "image_url": None,
                "sheet_adp": 14,
                "sheet_projected_season_points": 340.0,
            },
        ],
    )
    assert response.status_code == 201, response.text

    available = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"search": "arch m", "limit": 10},
        headers=auth_headers(token),
    )
    assert available.status_code == 200, available.text
    rows = available.json()["data"]

    assert len(rows) == 1
    assert rows[0]["name"] == "Arch Manning"
    assert rows[0]["school"] == "TEXAS"
    assert rows[0]["sheet_adp"] == 14
    assert rows[0]["sheet_projected_season_points"] == 340.0
    assert rows[0]["board_rank"] == 1


def test_available_mock_players_excludes_generated_smoke_rows(client):
    token = create_user_and_token(client, "smoke-pool")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": "Smoke Player 1780924455-1",
                "position": "RB",
                "school": "Smoke School 1",
                "image_url": None,
                "sheet_adp": 1,
                "sheet_projected_season_points": 299.0,
            },
            {
                "external_id": None,
                "name": "Smoke Raw Player 1780924535-1",
                "position": "RB",
                "school": "Smoke Raw School 1",
                "image_url": None,
                "sheet_adp": 2,
                "sheet_projected_season_points": 298.0,
            },
            {
                "external_id": None,
                "name": "Ahmad Hardy",
                "position": "RB",
                "school": "Missouri",
                "image_url": None,
                "sheet_adp": 3,
                "sheet_projected_season_points": 347.4,
            },
        ],
    )
    assert response.status_code == 201, response.text

    available = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"limit": 10},
        headers=auth_headers(token),
    )

    assert available.status_code == 200, available.text
    rows = available.json()["data"]
    assert [row["name"] for row in rows] == ["Ahmad Hardy"]
    assert rows[0]["board_rank"] == 1


def test_available_mock_position_search_uses_master_board_ranks(client):
    token = create_user_and_token(client, "board-rank-search")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": "Top RB",
                "position": "RB",
                "school": "School A",
                "image_url": None,
                "sheet_adp": 1,
                "sheet_projected_season_points": 350.0,
            },
            {
                "external_id": None,
                "name": "First QB",
                "position": "QB",
                "school": "School B",
                "image_url": None,
                "sheet_adp": 2,
                "sheet_projected_season_points": 340.0,
            },
            {
                "external_id": None,
                "name": "Second QB",
                "position": "QB",
                "school": "School C",
                "image_url": None,
                "sheet_adp": 2,
                "sheet_projected_season_points": 330.0,
            },
            {
                "external_id": None,
                "name": "Top WR",
                "position": "WR",
                "school": "School D",
                "image_url": None,
                "sheet_adp": 3,
                "sheet_projected_season_points": 320.0,
            },
        ],
    )
    assert response.status_code == 201, response.text

    master = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"limit": 10},
        headers=auth_headers(token),
    )
    assert master.status_code == 200, master.text
    master_rank_by_name = {row["name"]: row["board_rank"] for row in master.json()["data"]}

    qb_search = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"search": "QB", "limit": 10},
        headers=auth_headers(token),
    )
    assert qb_search.status_code == 200, qb_search.text
    qbs = qb_search.json()["data"]
    assert [row["name"] for row in qbs] == ["First QB", "Second QB"]
    assert [row["board_rank"] for row in qbs] == [master_rank_by_name["First QB"], master_rank_by_name["Second QB"]]
    assert len({row["board_rank"] for row in qbs}) == len(qbs)


def test_available_mock_players_can_return_more_than_top_100(client):
    token = create_user_and_token(client, "mock-more-than-100")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    create_players(client, 150)

    response = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"limit": 150},
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["limit"] == 150
    assert len(payload["data"]) == 150
    assert payload["data"][-1]["board_rank"] == 150


def test_single_player_bot_at_pick_one_auto_picks_after_intermission(client, db_session):
    token = create_user_and_token(client, "single-bot-one")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    player_ids = create_players(client, 12)

    participants = (
        db_session.query(MockDraftParticipant)
        .filter(MockDraftParticipant.mock_draft_id == created["mock_draft_id"])
        .order_by(MockDraftParticipant.participant_type.asc(), MockDraftParticipant.id.asc())
        .all()
    )
    bots = [participant for participant in participants if participant.participant_type == "bot"]
    humans = [participant for participant in participants if participant.participant_type == "human"]
    assert bots and humans
    for participant in participants:
        participant.draft_position = None
    db_session.commit()

    bots[0].draft_position = 1
    humans[0].draft_position = 2
    for index, bot in enumerate(bots[1:], start=3):
        bot.draft_position = index
    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None
    session_row.draft_order_locked = True
    session_row.is_locked = True
    session_row.intermission_ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(session_row)
    db_session.commit()

    live_room = client.get(f"/mock-drafts/{created['mock_draft_id']}/room", headers=auth_headers(token))
    assert live_room.status_code == 200, live_room.text
    live_payload = live_room.json()
    assert live_payload["status"] == "live"
    assert live_payload["current_overall_pick"] == 1
    assert live_payload["current_participant_type"] == "bot"
    assert live_payload["current_pick_started_at"] is not None

    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None
    session_row.current_pick_started_at = datetime.now(timezone.utc) - timedelta(seconds=3)
    session_row.current_pick_expires_at = datetime.now(timezone.utc) + timedelta(seconds=27)
    db_session.add(session_row)
    db_session.commit()

    auto = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={"force": False, "expected_overall_pick": 1},
        headers=auth_headers(token),
    )
    assert auto.status_code == 200, auto.text
    payload = auto.json()
    assert payload["current_overall_pick"] == 2
    assert len(payload["picks"]) == 1
    assert payload["picks"][0]["overall_pick"] == 1
    assert payload["picks"][0]["participant_id"] == bots[0].id
    assert payload["picks"][0]["player_id"] == player_ids[0]
    assert payload["current_pick_started_at"] is not None
    assert payload["current_pick_expires_at"] is not None

    stale = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={"force": True, "expected_overall_pick": 1},
        headers=auth_headers(token),
    )
    assert stale.status_code == 409
    picks = db_session.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == created["mock_draft_id"]).all()
    assert len(picks) == 1


def test_single_player_bot_first_pick_force_auto_picks_immediately(client, db_session):
    token = create_user_and_token(client, "single-bot-force")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    create_players(client, 12)

    participants = (
        db_session.query(MockDraftParticipant)
        .filter(MockDraftParticipant.mock_draft_id == created["mock_draft_id"])
        .order_by(MockDraftParticipant.participant_type.asc(), MockDraftParticipant.id.asc())
        .all()
    )
    bots = [participant for participant in participants if participant.participant_type == "bot"]
    humans = [participant for participant in participants if participant.participant_type == "human"]
    assert bots and humans
    for participant in participants:
        participant.draft_position = None
    db_session.commit()

    bots[0].draft_position = 1
    humans[0].draft_position = 2
    for index, bot in enumerate(bots[1:], start=3):
        bot.draft_position = index

    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None
    session_row.draft_order_locked = True
    session_row.is_locked = True
    session_row.intermission_ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(session_row)
    db_session.commit()

    live_room = client.get(f"/mock-drafts/{created['mock_draft_id']}/room", headers=auth_headers(token))
    assert live_room.status_code == 200, live_room.text
    assert live_room.json()["current_participant_type"] == "bot"

    auto = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={"force": True, "expected_overall_pick": 1},
        headers=auth_headers(token),
    )
    assert auto.status_code == 200, auto.text
    payload = auto.json()
    assert payload["current_overall_pick"] == 2
    assert len(payload["picks"]) == 1
    assert payload["picks"][0]["overall_pick"] == 1
    assert payload["picks"][0]["participant_id"] == bots[0].id


def test_auto_pick_works_without_player_adp_or_projection(client, db_session):
    token = create_user_and_token(client, "auto-no-rank")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": "Zeta Fallback",
                "position": "RB",
                "school": "Fallback State",
                "image_url": None,
                "sheet_adp": None,
                "sheet_projected_season_points": None,
            },
            {
                "external_id": None,
                "name": "Alpha Fallback",
                "position": "WR",
                "school": "Fallback Tech",
                "image_url": None,
                "sheet_adp": None,
                "sheet_projected_season_points": None,
            },
        ],
    )
    assert response.status_code == 201, response.text
    room = move_to_live(client, db_session, token, created["mock_draft_id"])
    assert room["status"] == "live"

    auto = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={"force": True, "expected_overall_pick": 1},
        headers=auth_headers(token),
    )

    assert auto.status_code == 200, auto.text
    payload = auto.json()
    assert len(payload["picks"]) == 1
    assert payload["picks"][0]["player_name"] == "Alpha Fallback"
    assert payload["current_overall_pick"] == 2


def test_single_player_user_pick_and_available_players_are_mock_scoped(client, db_session):
    token = create_user_and_token(client, "single-user-pick")
    league = create_league(client, token)
    league_before = db_session.get(League, league["id"]).status
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    player_ids = create_players(client, 8)
    move_to_live(client, db_session, token, created["mock_draft_id"])

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

    pick = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/picks",
        json={"player_id": player_ids[0]},
        headers=auth_headers(token),
    )
    assert pick.status_code == 200, pick.text
    assert pick.json()["picks"][0]["player_id"] == player_ids[0]

    available = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"limit": 100},
        headers=auth_headers(token),
    )
    assert available.status_code == 200, available.text
    available_ids = {row["id"] for row in available.json()["data"]}
    assert player_ids[0] not in available_ids
    assert set(player_ids[1:]).issubset(available_ids)
    assert db_session.query(RosterEntry).count() == 0
    assert db_session.query(DraftPick).count() == 0
    assert db_session.query(MockDraftRosterEntry).count() == 0
    assert db_session.get(League, league["id"]).status == league_before


def test_single_player_user_pick_must_fit_remaining_roster_position(client, db_session):
    token = create_user_and_token(client, "single-position-fit")
    created = create_mock_draft(client, token, team_count=4, round_count=1, mode="single_player")
    player_payload = [
        {"name": "Filled QB", "position": "QB"},
        {"name": "Filled RB One", "position": "RB"},
        {"name": "Filled RB Two", "position": "RB"},
        {"name": "Filled WR One", "position": "WR"},
        {"name": "Filled WR Two", "position": "WR"},
        {"name": "Filled TE", "position": "TE"},
        {"name": "Filled Flex", "position": "RB"},
        {"name": "Filled Bench QB", "position": "QB"},
        {"name": "Filled Bench WR", "position": "WR"},
        {"name": "Filled Bench TE", "position": "TE"},
        {"name": "Filled Bench RB", "position": "RB"},
        {"name": "Filled Bench WR Two", "position": "WR"},
        {"name": "Wrong Position Candidate", "position": "RB"},
        {"name": "Kicker Candidate", "position": "K"},
    ]
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": row["name"],
                "position": row["position"],
                "school": "Roster Fit State",
                "image_url": None,
                "sheet_adp": index + 1,
                "sheet_projected_season_points": float(300 - index),
            }
            for index, row in enumerate(player_payload)
        ],
    )
    assert response.status_code == 201, response.text
    players = response.json()
    move_to_live(client, db_session, token, created["mock_draft_id"])

    participants = (
        db_session.query(MockDraftParticipant)
        .filter(MockDraftParticipant.mock_draft_id == created["mock_draft_id"])
        .order_by(MockDraftParticipant.is_host.desc(), MockDraftParticipant.id.asc())
        .all()
    )
    host = next(participant for participant in participants if participant.participant_type == "human")
    bots = [participant for participant in participants if participant.id != host.id]
    for participant in participants:
        participant.draft_position = None
        db_session.add(participant)
    db_session.flush()
    for index, bot in enumerate(bots, start=1):
        bot.draft_position = index
        db_session.add(bot)
    host.draft_position = 4
    db_session.add(host)
    for index, player in enumerate(players[:12], start=1):
        db_session.add(
            MockDraftPick(
                session_id=created["mock_draft_id"],
                mock_draft_id=created["mock_draft_id"],
                participant_id=host.id,
                seat_id=None,
                player_id=player["id"],
                round_number=1,
                round_pick=index,
                overall_pick=index,
                pick_source="human",
            )
        )
    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None
    session_row.current_overall_pick = 13
    session_row.current_pick_started_at = datetime.now(timezone.utc)
    session_row.current_pick_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    db_session.add(session_row)
    db_session.commit()

    wrong_position = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/picks",
        json={"player_id": players[12]["id"]},
        headers=auth_headers(token),
    )
    assert wrong_position.status_code == 409
    assert "cannot fit" in wrong_position.text
    assert db_session.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == created["mock_draft_id"]).count() == 12

    kicker = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/picks",
        json={"player_id": players[13]["id"]},
        headers=auth_headers(token),
    )
    assert kicker.status_code == 200, kicker.text
    assert kicker.json()["picks"][-1]["player_name"] == "Kicker Candidate"


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


def test_human_timer_auto_pick_uses_first_valid_queued_player(client, db_session):
    host_token = create_user_and_token(client, "auto-queue")
    created = create_mock_draft(client, host_token, team_count=4, round_count=1, mode="single_player")
    player_ids = create_players(client, 20)

    participants = db_session.query(MockDraftParticipant).filter(MockDraftParticipant.mock_draft_id == created["mock_draft_id"]).all()
    human = next(participant for participant in participants if participant.participant_type == "human")
    bots = [participant for participant in participants if participant.participant_type == "bot"]
    for participant in participants:
        participant.draft_position = None
    db_session.commit()

    human.draft_position = 1
    for index, bot in enumerate(bots, start=2):
        bot.draft_position = index

    now = datetime.now(timezone.utc)
    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row is not None
    session_row.status = "live"
    session_row.draft_order_locked = True
    session_row.is_locked = True
    session_row.current_overall_pick = 1
    session_row.current_pick_started_at = now - timedelta(seconds=31)
    session_row.current_pick_expires_at = now - timedelta(seconds=1)
    db_session.add(session_row)
    db_session.commit()

    queued_player_id = player_ids[5]
    invalid_player_id = max(player_ids) + 100_000
    response = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={
            "expected_overall_pick": 1,
            "preferred_player_ids": [invalid_player_id, queued_player_id],
        },
        headers=auth_headers(host_token),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["picks"]) == 1
    assert payload["picks"][0]["participant_id"] == human.id
    assert payload["picks"][0]["player_id"] == queued_player_id
    assert payload["picks"][0]["pick_source"] == "auto_timer"
    assert payload["current_overall_pick"] == 2


def test_auto_pick_integrity_error_returns_409_without_partial_pick(client, db_session, monkeypatch):
    host_token = create_user_and_token(client, "auto-conflict")
    created = create_mock_draft(client, host_token, team_count=4, round_count=2, mode="single_player")
    create_players(client, 20)
    room = move_to_live(client, db_session, host_token, created["mock_draft_id"])
    assert room["status"] == "live"

    def raise_integrity_error(*args, **kwargs):
        raise IntegrityError("insert mock draft pick", {}, Exception("forced conflict"))

    monkeypatch.setattr(mock_draft_service, "_create_pick", raise_integrity_error)

    response = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={"force": True, "expected_overall_pick": room["current_overall_pick"]},
        headers=auth_headers(host_token),
    )

    assert response.status_code == 409
    assert "Duplicate auto-pick request" in response.text
    assert db_session.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == created["mock_draft_id"]).count() == 0


def test_mock_draft_pick_seat_id_is_nullable_for_standalone_picks():
    assert MockDraftPick.__table__.c.seat_id.nullable is True


def test_available_player_board_ranks_do_not_compress_after_picks(client, db_session):
    host_token = create_user_and_token(client, "stable-ranks")
    created = create_mock_draft(client, host_token, team_count=4, round_count=2, mode="single_player")
    create_players(client, 20)
    room = move_to_live(client, db_session, host_token, created["mock_draft_id"])
    assert room["status"] == "live"

    first_pick = client.post(
        f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
        json={"force": True, "expected_overall_pick": room["current_overall_pick"]},
        headers=auth_headers(host_token),
    )
    assert first_pick.status_code == 200, first_pick.text
    assert first_pick.json()["picks"][0]["player_name"] == "Mock Player 1"

    available = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"limit": 3},
        headers=auth_headers(host_token),
    )

    assert available.status_code == 200, available.text
    players = available.json()["data"]
    assert players[0]["name"] == "Mock Player 2"
    assert players[0]["board_rank"] == 2
    assert players[1]["name"] == "Mock Player 3"
    assert players[1]["board_rank"] == 3


def test_available_players_positions_filter_finds_late_kicker_need(client):
    host_token = create_user_and_token(client, "kicker-filter")
    created = create_mock_draft(client, host_token, team_count=4, round_count=1, mode="single_player")
    payload = [
        {
            "external_id": None,
            "name": f"Ranked RB {index + 1}",
            "position": "RB",
            "school": f"School {index + 1}",
            "image_url": None,
            "sheet_adp": index + 1,
            "sheet_projected_season_points": float(400 - index),
        }
        for index in range(510)
    ]
    payload.append(
        {
            "external_id": None,
            "name": "Late Board Kicker",
            "position": "K",
            "school": "Special Teams",
            "image_url": None,
            "sheet_adp": 999,
            "sheet_projected_season_points": 90.0,
        }
    )
    players_response = client.post("/players", json=payload)
    assert players_response.status_code == 201, players_response.text

    generic_response = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"limit": 100},
        headers=auth_headers(host_token),
    )
    assert generic_response.status_code == 200, generic_response.text
    assert all(player["position"] != "K" for player in generic_response.json()["data"])

    kicker_response = client.get(
        f"/mock-drafts/{created['mock_draft_id']}/available-players",
        params={"limit": 100, "positions": "K"},
        headers=auth_headers(host_token),
    )
    assert kicker_response.status_code == 200, kicker_response.text
    kicker_players = kicker_response.json()["data"]
    assert [player["name"] for player in kicker_players] == ["Late Board Kicker"]
    assert kicker_players[0]["position"] == "K"


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


def test_single_player_completes_and_reset_restarts_without_real_writes(client, db_session):
    host_token = create_user_and_token(client, "single-reset")
    league = create_league(client, host_token)
    league_before = db_session.get(League, league["id"]).status
    created = create_mock_draft(client, host_token, team_count=4, round_count=1, mode="single_player")
    create_players(client, 60)
    room = move_to_live(client, db_session, host_token, created["mock_draft_id"])
    assert room["status"] == "live"

    total_picks = room["total_picks"]
    assert total_picks == 52
    for _index in range(total_picks):
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
    assert db_session.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == created["mock_draft_id"]).count() == total_picks
    assert db_session.query(RosterEntry).count() == 0
    assert db_session.query(DraftPick).count() == 0
    assert db_session.query(MockDraftRosterEntry).count() == 0
    assert db_session.get(League, league["id"]).status == league_before

    reset = client.post(f"/mock-drafts/{created['mock_draft_id']}/reset", headers=auth_headers(host_token))
    assert reset.status_code == 200, reset.text
    payload = reset.json()
    assert payload["status"] == "intermission"
    assert payload["phase_type"] == "prestart_countdown"
    assert payload["current_overall_pick"] == 1
    assert payload["picks"] == []
    assert len(payload["draft_order"]) == 4
    session_row = db_session.get(MockDraftSession, created["mock_draft_id"])
    assert session_row.completed_at is None
    assert session_row.history_email_sent_at is None
    assert 85 <= (session_row.intermission_ends_at - session_row.intermission_started_at).total_seconds() <= 95
    assert db_session.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == created["mock_draft_id"]).count() == 0
    assert db_session.query(RosterEntry).count() == 0
    assert db_session.query(DraftPick).count() == 0
    assert db_session.query(MockDraftRosterEntry).count() == 0
    assert db_session.get(League, league["id"]).status == league_before


def test_email_history_fallback_success_and_cleanup(client, db_session):
    host_token = create_user_and_token(client, "email-host")
    created = create_mock_draft(client, host_token, team_count=4, round_count=1)
    create_players(client, 60)
    room = move_to_live(client, db_session, host_token, created["mock_draft_id"])
    for _index in range(room["total_picks"]):
        response = client.post(
            f"/mock-drafts/{created['mock_draft_id']}/auto-pick",
            json={"force": True},
            headers=auth_headers(host_token),
        )
        assert response.status_code == 200
        room = response.json()
        if room["is_complete"]:
            break

    missing = client.post(f"/mock-drafts/{created['mock_draft_id']}/history/email", headers=auth_headers(host_token))
    assert missing.status_code == 503
    assert missing.json()["detail"]["history"]["pick_count"] == 52

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
