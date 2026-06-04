from datetime import datetime, timedelta, timezone

from api.app.api.routes import leagues as league_routes
from api.app.core.config import settings
from api.app.models.draft import Draft
from api.app.models.draft_team_queue_item import DraftTeamQueueItem
from api.app.models.league import League
from api.app.models.league_settings import LeagueSettings
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_league(client, token: str) -> dict:
    payload = {
        "basics": {
            "name": "Draft Test League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": False,
            "description": "Draft room league",
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
            "timezone": "America/Los_Angeles",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }
    response = client.post(
        "/leagues",
        json=payload,
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def create_player(client, name: str = "Arch Manning") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": "QB",
                "school": "Texas",
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def create_player_with_position(client, *, name: str, position: str, school: str = "Texas") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": position,
                "school": school,
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def create_players(client, total: int) -> list[int]:
    payload = []
    for index in range(total):
        payload.append(
            {
                "external_id": None,
                "name": f"Draft Player {index + 1}",
                "position": "QB",
                "school": f"School {index + 1}",
                "image_url": None,
            }
        )
    response = client.post("/players", json=payload)
    assert response.status_code == 201
    return [row["id"] for row in response.json()]


def force_draft_live(db_session, *, league_id: int) -> None:
    draft_row = db_session.query(Draft).filter(Draft.league_id == league_id).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()


def test_draft_pick_persists_and_creates_roster_entry(client, db_session):
    token = create_user_and_token(client, "draft")
    league = create_league(client, token)
    player_id = create_player(client)
    force_draft_live(db_session, league_id=league["id"])

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    room = room_response.json()
    assert room["picks"] == []
    assert room["can_make_pick"] is True
    assert room["user_team_id"] is not None

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 201
    updated_room = pick_response.json()
    assert len(updated_room["picks"]) == 1
    assert updated_room["picks"][0]["player_id"] == player_id
    assert updated_room["picks"][0]["team_id"] == updated_room["user_team_id"]

    roster_response = client.get(
        f"/teams/{updated_room['user_team_id']}/roster",
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 200
    roster = roster_response.json()
    assert roster["total"] == 1
    assert roster["data"][0]["player"]["id"] == player_id


def test_manual_pick_resets_persisted_pick_timer(client, db_session):
    token = create_user_and_token(client, "manual-timer")
    league = create_league(client, token)
    player_id = create_player(client, "Timer Reset QB")
    force_draft_live(db_session, league_id=league["id"])

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    assert pick_response.status_code == 201
    room = pick_response.json()
    assert room["current_pick"] == 2
    assert room["current_pick_started_at"] is not None
    assert room["current_pick_expires_at"] is not None
    assert room["seconds_remaining"] > 0


def test_auto_pick_endpoint_resets_timer(client, db_session):
    token = create_user_and_token(client, "auto-endpoint")
    league = create_league(client, token)
    create_players(client, 12)
    force_draft_live(db_session, league_id=league["id"])

    response = client.post(
        f"/leagues/{league['id']}/draft-picks/auto",
        json={"force": True},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    room = response.json()
    assert len(room["picks"]) == 1
    assert room["current_pick"] == 2
    assert room["current_pick_started_at"] is not None
    assert room["current_pick_expires_at"] is not None


def test_full_156_pick_draft_simulation_completes(client, db_session):
    token = create_user_and_token(client, "full-156")
    league = create_league(client, token)
    create_players(client, 180)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={"team_count": 12, "reset_existing": True, "start_now": True, "mock_team_prefix": "CPU Team"},
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    settings_row.roster_slots_json = {"QB": 13}
    db_session.add(settings_row)
    db_session.commit()
    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    db_session.commit()

    room = setup_response.json()
    for _index in range(156):
        response = client.post(
            f"/leagues/{league['id']}/draft-picks/auto",
            json={"force": True},
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        room = response.json()
        if room["is_complete"]:
            break

    assert len(room["picks"]) == 156
    assert room["status"] == "completed"
    assert room["is_complete"] is True
    assert room["can_exit"] is True
    assert room["current_pick_expires_at"] is None


def test_draft_history_payload_and_email_log(client, db_session):
    token = create_user_and_token(client, "history")
    league = create_league(client, token)
    player_id = create_player(client, "History QB")
    force_draft_live(db_session, league_id=league["id"])
    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 201
    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "completed"
    draft_row.completed_at = datetime.now(timezone.utc)
    db_session.add(draft_row)
    db_session.commit()

    history_response = client.get(
        f"/leagues/{league['id']}/draft-history",
        headers=auth_headers(token),
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["pick_count"] == 1
    assert "History QB" in history["plain_text"]
    assert history["rounds"][0]["picks"][0]["player_name"] == "History QB"

    prior_resend_key = settings.resend_api_key
    settings.resend_api_key = "test-key"
    try:
        email_response = client.post(
            f"/leagues/{league['id']}/draft-history/email",
            json={"send_to_account_email": True},
            headers=auth_headers(token),
        )
    finally:
        settings.resend_api_key = prior_resend_key
    assert email_response.status_code == 200
    assert email_response.json()["sent"] is True


def test_draft_room_requires_membership(client):
    owner_token = create_user_and_token(client, "draft-owner")
    outsider_token = create_user_and_token(client, "draft-outsider")
    league = create_league(client, owner_token)

    response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_practice_setup_resets_draft_and_builds_mock_teams(client, db_session):
    token = create_user_and_token(client, "practice")
    league = create_league(client, token)
    player_id = create_player(client, "Practice QB")
    force_draft_live(db_session, league_id=league["id"])

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 201
    assert len(pick_response.json()["picks"]) == 1

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": True,
            "mock_team_prefix": "Practice Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    room = setup_response.json()
    assert room["status"] == "countdown"
    assert room["current_pick"] == 1
    assert len(room["picks"]) == 0
    assert len(room["teams"]) == 4
    assert any(team["owner_user_id"] is None for team in room["teams"])

    roster_response = client.get(
        f"/teams/{room['user_team_id']}/roster",
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 200
    assert roster_response.json()["total"] == 0


def test_practice_setup_normalizes_to_manager_one_plus_unique_auto_managers(client):
    token = create_user_and_token(client, "manager-normalize")
    league = create_league(client, token)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 12,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "Auto Manager",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    room = setup_response.json()
    assert len(room["teams"]) == 12

    owned_teams = [team for team in room["teams"] if team["owner_user_id"] is not None]
    assert len(owned_teams) == 1
    assert owned_teams[0]["name"] == "Manager 1"

    team_names = [team["name"] for team in room["teams"]]
    assert len(team_names) == len(set(team_names))
    assert "Manager 1" in team_names
    for index in range(2, 13):
        assert f"Auto Manager {index}" in team_names


def test_draft_room_total_rounds_equals_roster_slot_count(client):
    token = create_user_and_token(client, "round-count")
    league = create_league(client, token)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "Auto Manager",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    room = setup_response.json()
    expected_rounds = sum(int(value) for key, value in room["roster_slots"].items() if key != "IR")
    assert room["total_rounds"] == expected_rounds
    assert room["total_picks"] == expected_rounds * len(room["teams"])


def test_draft_room_timeout_autopicks_current_team_using_top_available_player(client, db_session):
    token = create_user_and_token(client, "solo-auto")
    league = create_league(client, token)
    player_ids = create_players(client, 24)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    room = setup_response.json()
    assert room["current_pick"] == 1
    assert room["user_team_id"] is not None

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=95)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()
    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None
    changed = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed is True
    db_session.commit()

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    updated_room = room_response.json()
    assert updated_room["status"] in {"live", "completed"}
    assert len(updated_room["picks"]) == 1
    auto_pick = updated_room["picks"][0]
    assert auto_pick["player_id"] == player_ids[0]
    assert auto_pick["made_by_user_id"] is None
    assert updated_room["current_pick"] == 2


def test_sheet_sync_projection_override_boosts_hollywood_smothers_only():
    rows = [
        {"name": "Hollywood Smothers", "projected_fantasy_points": 212.0, "position": "RB"},
        {"name": "Another Player", "projected_fantasy_points": 212.0, "position": "RB"},
    ]
    league_routes._apply_projection_name_overrides(rows)
    assert rows[0]["projected_fantasy_points"] == 216.0
    assert rows[1]["projected_fantasy_points"] == 212.0


def test_timeout_autopick_ignores_queue_and_uses_top_board_player_for_expired_user_turn(client, db_session):
    token = create_user_and_token(client, "timeout-board-over-queue")
    league = create_league(client, token)
    player_ids = create_players(client, 24)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    room = setup_response.json()
    user_team_id = int(room["user_team_id"])
    ordered_ids = [user_team_id] + [int(team_id) for team_id in room["draft_order"] if int(team_id) != user_team_id]
    league_routes._persist_draft_order(
        db_session,
        league_id=league["id"],
        ordered_team_ids=ordered_ids,
        strategy="random",
    )
    db_session.commit()

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    db_session.flush()

    # Queue the second player; timeout must still take player_ids[0] from top ADP board order.
    db_session.add(
        DraftTeamQueueItem(
            draft_id=draft_row.id,
            team_id=user_team_id,
            player_id=player_ids[1],
            priority=1,
        )
    )
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=95)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()

    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None
    changed = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed is True
    db_session.commit()

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    updated_room = room_response.json()
    assert len(updated_room["picks"]) == 1
    assert updated_room["picks"][0]["team_id"] == user_team_id
    assert updated_room["picks"][0]["player_id"] == player_ids[0]
    assert updated_room["picks"][0]["player_id"] != player_ids[1]


def test_manual_pick_is_blocked_when_pick_clock_is_expired(client, db_session):
    token = create_user_and_token(client, "auto-lock")
    league = create_league(client, token)
    player_ids = create_players(client, 12)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=95)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()

    blocked_pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_ids[0]},
        headers=auth_headers(token),
    )
    assert blocked_pick_response.status_code == 409
    assert "Pick clock expired" in blocked_pick_response.json()["detail"]


def test_countdown_transition_is_rejected_when_existing_picks_are_present(client, db_session):
    token = create_user_and_token(client, "countdown-blocked")
    league = create_league(client, token)
    player_id = create_player(client, "Countdown Block QB")
    force_draft_live(db_session, league_id=league["id"])

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 201

    countdown_response = client.post(
        f"/leagues/{league['id']}/draft-room/status",
        json={"status": "countdown"},
        headers=auth_headers(token),
    )
    assert countdown_response.status_code == 409
    assert "Cannot start countdown with existing picks" in countdown_response.json()["detail"]


def test_timeout_runner_commits_only_one_pick_per_expired_cycle(client, db_session):
    token = create_user_and_token(client, "single-timeout")
    league = create_league(client, token)
    create_players(client, 30)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=95)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()

    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None

    first_changed = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert first_changed is True
    db_session.commit()

    room_after_first = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_after_first.status_code == 200
    first_room_payload = room_after_first.json()
    assert len(first_room_payload["picks"]) == 1
    assert first_room_payload["current_pick"] == 2

    second_changed_without_new_expiry = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert second_changed_without_new_expiry is False
    db_session.commit()

    room_after_second = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_after_second.status_code == 200
    second_room_payload = room_after_second.json()
    assert len(second_room_payload["picks"]) == 1
    assert second_room_payload["current_pick"] == 2


def test_cpu_autopick_triggers_at_88_seconds_not_89_seconds(client, db_session):
    token = create_user_and_token(client, "cpu-threshold")
    league = create_league(client, token)
    create_players(client, 30)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "Auto Manager",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    setup_room = setup_response.json()
    order = [int(team_id) for team_id in setup_room["draft_order"]]
    user_team_id = int(setup_room["user_team_id"])
    first_cpu_team_id = next(team_id for team_id in order if team_id != user_team_id)
    ordered_ids = [first_cpu_team_id] + [team_id for team_id in order if team_id != first_cpu_team_id]
    league_routes._persist_draft_order(
        db_session,
        league_id=league["id"],
        ordered_team_ids=ordered_ids,
        strategy="random",
    )
    db_session.commit()

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()

    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None

    # 89s remaining on 90s clock: no CPU pick yet.
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(timer_row)
    db_session.commit()
    changed_89 = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed_89 is False
    db_session.commit()

    room_after_89 = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_after_89.status_code == 200
    assert len(room_after_89.json()["picks"]) == 0

    # 88s remaining on 90s clock: CPU pick triggers.
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    db_session.add(timer_row)
    db_session.commit()
    changed_88 = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed_88 is True
    db_session.commit()

    room_after_88 = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_after_88.status_code == 200
    assert len(room_after_88.json()["picks"]) == 1


def test_prestart_countdown_allows_zero_picks_until_countdown_completes(client, db_session):
    token = create_user_and_token(client, "countdown-zero-picks")
    league = create_league(client, token)
    create_players(client, 30)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200

    start_countdown_response = client.post(
        f"/leagues/{league['id']}/draft-room/status",
        json={"status": "countdown"},
        headers=auth_headers(token),
    )
    assert start_countdown_response.status_code == 200
    assert start_countdown_response.json()["status"] == "countdown"

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None

    # Countdown still running: no picks committed.
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=30)
    db_session.add(timer_row)
    db_session.commit()

    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None
    changed_while_counting_down = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed_while_counting_down is False
    db_session.commit()

    room_mid_countdown = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_mid_countdown.status_code == 200
    assert room_mid_countdown.json()["status"] == "countdown"
    assert len(room_mid_countdown.json()["picks"]) == 0

    # Countdown expires: transition to live only, still zero picks.
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=65)
    db_session.add(timer_row)
    db_session.commit()
    changed_on_countdown_expiry = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed_on_countdown_expiry is True
    db_session.commit()

    room_after_countdown = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_after_countdown.status_code == 200
    assert room_after_countdown.json()["status"] == "live"
    assert len(room_after_countdown.json()["picks"]) == 0


def test_scheduled_draft_does_not_auto_start_without_explicit_countdown(client, db_session):
    token = create_user_and_token(client, "scheduled-no-auto")
    league = create_league(client, token)
    create_players(client, 20)

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "scheduled"
    draft_row.draft_datetime_utc = datetime.now(timezone.utc) - timedelta(minutes=30)
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = None
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()

    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None
    changed = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed is False
    db_session.commit()

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    room = room_response.json()
    assert room["status"] == "scheduled"
    assert len(room["picks"]) == 0


def test_draft_lobby_slot_move_reorders_draft_order(client):
    token = create_user_and_token(client, "slot-move")
    league = create_league(client, token)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    room_before = setup_response.json()
    assert len(room_before["draft_order"]) == 4
    first_team = room_before["draft_order"][0]
    second_team = room_before["draft_order"][1]

    move_response = client.post(
        f"/leagues/{league['id']}/draft-room/slots/move",
        json={"from_slot": 1, "to_slot": 2},
        headers=auth_headers(token),
    )
    assert move_response.status_code == 200
    room_after = move_response.json()
    assert room_after["draft_order"][0] == second_team
    assert room_after["draft_order"][1] == first_team


def test_draft_room_exposes_phase_fields_and_uses_60s_prestart_countdown(client, db_session):
    token = create_user_and_token(client, "phase-fields")
    league = create_league(client, token)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200
    lobby_room = setup_response.json()
    assert lobby_room["status"] == "lobby_open"
    assert lobby_room["phase_type"] is None
    assert lobby_room["seconds_remaining"] is None

    countdown_response = client.post(
        f"/leagues/{league['id']}/draft-room/status",
        json={"status": "countdown"},
        headers=auth_headers(token),
    )
    assert countdown_response.status_code == 200

    countdown_room = countdown_response.json()
    assert countdown_room["status"] == "countdown"
    assert countdown_room["phase_type"] == "prestart_countdown"
    assert countdown_room["current_pick_timer_seconds"] == 90
    assert 50 <= int(countdown_room["seconds_remaining"] or 0) <= 60
    assert countdown_room["phase_seconds_remaining"] == countdown_room["seconds_remaining"]


def test_draft_lobby_join_and_ready_updates_presence_fields(client):
    token = create_user_and_token(client, "lobby-presence")
    league = create_league(client, token)

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(token),
    )
    assert setup_response.status_code == 200

    before_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert before_response.status_code == 200
    before_room = before_response.json()
    assert before_room["status"] == "lobby_open"
    # Auto teams count as joined/connected/ready. User team is not joined until explicit action.
    assert before_room["lobby_joined_count"] == 3
    assert before_room["lobby_ready_count"] == 3
    user_team = next(team for team in before_room["teams"] if team["owner_user_id"] is not None)
    assert user_team["lobby_joined"] is False
    assert user_team["lobby_ready"] is False

    join_response = client.post(
        f"/leagues/{league['id']}/draft-room/lobby/join",
        headers=auth_headers(token),
    )
    assert join_response.status_code == 200
    joined_room = join_response.json()
    assert joined_room["lobby_joined_count"] == 4
    joined_team = next(team for team in joined_room["teams"] if team["owner_user_id"] is not None)
    assert joined_team["lobby_joined"] is True
    assert joined_team["lobby_connected"] is True
    assert joined_team["lobby_ready"] is False

    ready_response = client.post(
        f"/leagues/{league['id']}/draft-room/lobby/ready",
        json={"ready": True},
        headers=auth_headers(token),
    )
    assert ready_response.status_code == 200
    ready_room = ready_response.json()
    assert ready_room["lobby_ready_count"] == 4
    ready_team = next(team for team in ready_room["teams"] if team["owner_user_id"] is not None)
    assert ready_team["lobby_ready"] is True


def test_draft_lobby_join_claims_unowned_team_for_member_without_owned_team(client):
    commissioner_token = create_user_and_token(client, "lobby-commissioner")
    member_token = create_user_and_token(client, "lobby-member")
    league = create_league(client, commissioner_token)

    join_league_response = client.post(
        f"/leagues/{league['id']}/join",
        headers=auth_headers(member_token),
    )
    assert join_league_response.status_code == 200

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(commissioner_token),
    )
    assert setup_response.status_code == 200

    join_response = client.post(
        f"/leagues/{league['id']}/draft-room/lobby/join",
        headers=auth_headers(member_token),
    )
    assert join_response.status_code == 200
    joined_room = join_response.json()
    claimed_team = next(team for team in joined_room["teams"] if team["owner_name"] == "Coachlobby-member")
    assert claimed_team["owner_user_id"] is not None
    assert claimed_team["lobby_joined"] is True
    assert claimed_team["lobby_connected"] is True


def test_draft_lobby_join_can_claim_unowned_team_while_live(client, db_session):
    commissioner_token = create_user_and_token(client, "lobby-live-commissioner")
    member_token = create_user_and_token(client, "lobby-live-member")
    league = create_league(client, commissioner_token)

    join_league_response = client.post(
        f"/leagues/{league['id']}/join",
        headers=auth_headers(member_token),
    )
    assert join_league_response.status_code == 200

    setup_response = client.post(
        f"/leagues/{league['id']}/draft-room/practice-setup",
        json={
            "team_count": 4,
            "reset_existing": True,
            "start_now": False,
            "mock_team_prefix": "CPU Team",
        },
        headers=auth_headers(commissioner_token),
    )
    assert setup_response.status_code == 200

    start_countdown_response = client.post(
        f"/leagues/{league['id']}/draft-room/status",
        json={"status": "active"},
        headers=auth_headers(commissioner_token),
    )
    assert start_countdown_response.status_code == 200
    assert start_countdown_response.json()["status"] == "countdown"

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=65)
    db_session.add(timer_row)
    db_session.commit()

    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None
    changed = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed is True
    db_session.commit()

    join_response = client.post(
        f"/leagues/{league['id']}/draft-room/lobby/join",
        headers=auth_headers(member_token),
    )
    assert join_response.status_code == 200
    joined_room = join_response.json()
    claimed_team = next(team for team in joined_room["teams"] if team["owner_name"] == "Coachlobby-live-member")
    assert claimed_team["owner_user_id"] is not None
    assert claimed_team["lobby_joined"] is True


def test_assign_roster_slot_prefers_flex_before_bench_for_wr_overflow(client, db_session):
    token = create_user_and_token(client, "flex-order")
    league = create_league(client, token)

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    settings_row.roster_slots_json = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "FLEX": 1,
        "K": 1,
        "BENCH": 5,
        "IR": 1,
    }
    db_session.add(settings_row)
    db_session.commit()

    team_row = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).first()
    assert team_row is not None

    wr_one = create_player_with_position(client, name="Flex WR One", position="WR")
    wr_two = create_player_with_position(client, name="Flex WR Two", position="WR")
    wr_three = create_player_with_position(client, name="Flex WR Three", position="WR")

    db_session.add_all(
        [
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=wr_one, slot="WR", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=wr_two, slot="WR", status="active"),
        ]
    )
    db_session.commit()

    # Incoming depth-label positions like WR3 should normalize and fill FLEX first.
    slot = league_routes._assign_roster_slot(db_session, settings_row, team_row.id, "WR3")
    assert slot == "FLEX"

    db_session.add(
        RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=wr_three, slot="FLEX", status="active")
    )
    db_session.commit()

    # Once FLEX is full, overflow should go to BENCH.
    bench_slot = league_routes._assign_roster_slot(db_session, settings_row, team_row.id, "WR4")
    assert bench_slot == "BENCH"


def test_assign_roster_slot_prefers_flex_before_bench_for_rb_overflow(client, db_session):
    token = create_user_and_token(client, "flex-rb")
    league = create_league(client, token)

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    settings_row.roster_slots_json = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "FLEX": 1,
        "K": 1,
        "BENCH": 5,
        "IR": 1,
    }
    db_session.add(settings_row)
    db_session.commit()

    team_row = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).first()
    assert team_row is not None

    rb_one = create_player_with_position(client, name="Flex RB One", position="RB")
    rb_two = create_player_with_position(client, name="Flex RB Two", position="RB")
    rb_three = create_player_with_position(client, name="Flex RB Three", position="RB")

    db_session.add_all(
        [
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_one, slot="RB", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_two, slot="RB", status="active"),
        ]
    )
    db_session.commit()

    slot = league_routes._assign_roster_slot(db_session, settings_row, team_row.id, "RB3")
    assert slot == "FLEX"

    db_session.add(
        RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_three, slot="FLEX", status="active")
    )
    db_session.commit()

    bench_slot = league_routes._assign_roster_slot(db_session, settings_row, team_row.id, "RB4")
    assert bench_slot == "BENCH"


def test_assign_roster_slot_prefers_flex_before_bench_for_te_overflow(client, db_session):
    token = create_user_and_token(client, "flex-te")
    league = create_league(client, token)

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    settings_row.roster_slots_json = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "FLEX": 1,
        "K": 1,
        "BENCH": 5,
        "IR": 1,
    }
    db_session.add(settings_row)
    db_session.commit()

    team_row = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).first()
    assert team_row is not None

    te_one = create_player_with_position(client, name="Flex TE One", position="TE")
    te_two = create_player_with_position(client, name="Flex TE Two", position="TE")

    db_session.add(
        RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=te_one, slot="TE", status="active")
    )
    db_session.commit()

    slot = league_routes._assign_roster_slot(db_session, settings_row, team_row.id, "TE2")
    assert slot == "FLEX"

    db_session.add(
        RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=te_two, slot="FLEX", status="active")
    )
    db_session.commit()

    bench_slot = league_routes._assign_roster_slot(db_session, settings_row, team_row.id, "TE3")
    assert bench_slot == "BENCH"


def test_can_draft_position_blocks_position_when_only_ir_is_open(client, db_session):
    token = create_user_and_token(client, "rb-full-ir-open")
    league = create_league(client, token)

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    settings_row.roster_slots_json = {
        "QB": 1,
        "RB": 1,
        "WR": 0,
        "TE": 0,
        "FLEX": 1,
        "K": 0,
        "BENCH": 1,
        "IR": 1,
    }
    db_session.add(settings_row)
    db_session.commit()

    team_row = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).first()
    assert team_row is not None

    rb_one = create_player_with_position(client, name="Full RB One", position="RB")
    rb_flex = create_player_with_position(client, name="Full RB Flex", position="RB")
    rb_bench = create_player_with_position(client, name="Full RB Bench", position="RB")
    db_session.add_all(
        [
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_one, slot="RB", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_flex, slot="FLEX", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_bench, slot="BENCH", status="active"),
        ]
    )
    db_session.commit()

    roster_entries = db_session.query(RosterEntry).filter(RosterEntry.team_id == team_row.id).all()
    fit = league_routes.can_draft_position("RB", roster_entries, settings_row)

    assert fit.can_draft is False
    assert fit.destination_slot is None
    assert fit.reason == league_routes.DRAFT_POSITION_FULL_REASON


def test_manual_pick_blocks_position_when_active_manager_has_no_valid_slot(client, db_session):
    token = create_user_and_token(client, "manual-rb-full")
    league = create_league(client, token)

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    settings_row.roster_slots_json = {
        "QB": 1,
        "RB": 1,
        "WR": 0,
        "TE": 0,
        "FLEX": 1,
        "K": 0,
        "BENCH": 1,
        "IR": 1,
    }
    db_session.add(settings_row)
    db_session.commit()

    team_row = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).first()
    assert team_row is not None

    rb_one = create_player_with_position(client, name="Manual Full RB One", position="RB")
    rb_flex = create_player_with_position(client, name="Manual Full RB Flex", position="RB")
    rb_bench = create_player_with_position(client, name="Manual Full RB Bench", position="RB")
    blocked_rb = create_player_with_position(client, name="Manual Blocked RB", position="RB")
    db_session.add_all(
        [
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_one, slot="RB", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_flex, slot="FLEX", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_bench, slot="BENCH", status="active"),
        ]
    )
    db_session.commit()
    force_draft_live(db_session, league_id=league["id"])

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    room = room_response.json()
    assert room["position_eligibility"]["RB"]["can_draft"] is False
    assert room["position_eligibility"]["RB"]["reason"] == "Roster full for this position"
    assert room["position_eligibility"]["QB"]["can_draft"] is True

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": blocked_rb},
        headers=auth_headers(token),
    )

    assert pick_response.status_code == 400
    assert pick_response.json()["detail"] == league_routes.DRAFT_POSITION_FULL_REASON


def test_timeout_autopick_skips_players_that_do_not_fit_active_roster(client, db_session):
    token = create_user_and_token(client, "auto-skip-rb-full")
    league = create_league(client, token)

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    settings_row.roster_slots_json = {
        "QB": 1,
        "RB": 1,
        "WR": 0,
        "TE": 0,
        "FLEX": 1,
        "K": 0,
        "BENCH": 1,
        "IR": 1,
    }
    db_session.add(settings_row)
    db_session.commit()

    team_row = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).first()
    assert team_row is not None

    rb_one = create_player_with_position(client, name="Auto Full RB One", position="RB")
    rb_flex = create_player_with_position(client, name="Auto Full RB Flex", position="RB")
    rb_bench = create_player_with_position(client, name="Auto Full RB Bench", position="RB")
    skipped_rb = create_player_with_position(client, name="Auto Skipped RB", position="RB")
    selected_qb = create_player_with_position(client, name="Auto Selected QB", position="QB")
    db_session.add_all(
        [
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_one, slot="RB", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_flex, slot="FLEX", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=rb_bench, slot="BENCH", status="active"),
        ]
    )
    db_session.query(Player).filter(Player.id == skipped_rb).update(
        {"sheet_adp": 1.0, "sheet_projected_season_points": 99.0}
    )
    db_session.query(Player).filter(Player.id == selected_qb).update(
        {"sheet_adp": 2.0, "sheet_projected_season_points": 98.0}
    )
    db_session.commit()

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=95)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()

    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None
    changed = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed is True
    db_session.commit()

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    room = room_response.json()
    assert len(room["picks"]) == 1
    assert room["picks"][0]["player_id"] == selected_qb

    selected_entry = (
        db_session.query(RosterEntry)
        .filter(
            RosterEntry.league_id == league["id"],
            RosterEntry.team_id == team_row.id,
            RosterEntry.player_id == selected_qb,
        )
        .first()
    )
    assert selected_entry is not None
    assert selected_entry.slot == "QB"


def test_manual_pick_uses_flex_before_bench_when_wr_slots_full(client, db_session):
    token = create_user_and_token(client, "manual-flex")
    league = create_league(client, token)

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    # Use legacy-style labels to ensure canonical slot handling still honors FLEX before BENCH.
    settings_row.roster_slots_json = {
        "QB1": 1,
        "RB1": 1,
        "RB2": 1,
        "WR1": 1,
        "WR2": 1,
        "TE1": 1,
        "FLEX1": 1,
        "K1": 1,
        "BENCH1": 1,
        "BENCH2": 1,
        "BENCH3": 1,
        "BENCH4": 1,
        "BENCH5": 1,
        "IR1": 1,
    }
    db_session.add(settings_row)
    db_session.commit()

    team_row = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).first()
    assert team_row is not None

    wr_one = create_player_with_position(client, name="Manual Flex WR One", position="WR")
    wr_two = create_player_with_position(client, name="Manual Flex WR Two", position="WR")
    wr_overflow = create_player_with_position(client, name="Manual Flex WR Overflow", position="WR")

    db_session.add_all(
        [
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=wr_one, slot="WR1", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=wr_two, slot="WR2", status="active"),
        ]
    )
    db_session.commit()
    force_draft_live(db_session, league_id=league["id"])

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": wr_overflow},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 201

    overflow_entry = (
        db_session.query(RosterEntry)
        .filter(
            RosterEntry.league_id == league["id"],
            RosterEntry.team_id == team_row.id,
            RosterEntry.player_id == wr_overflow,
        )
        .first()
    )
    assert overflow_entry is not None
    assert overflow_entry.slot == "FLEX"


def test_timeout_autopick_uses_flex_before_bench_when_wr_slots_full(client, db_session):
    token = create_user_and_token(client, "auto-flex")
    league = create_league(client, token)

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).first()
    assert settings_row is not None
    settings_row.roster_slots_json = {
        "QB1": 1,
        "RB1": 1,
        "RB2": 1,
        "WR1": 1,
        "WR2": 1,
        "TE1": 1,
        "FLEX1": 1,
        "K1": 1,
        "BENCH1": 1,
        "BENCH2": 1,
        "BENCH3": 1,
        "BENCH4": 1,
        "BENCH5": 1,
        "IR1": 1,
    }
    db_session.add(settings_row)
    db_session.commit()

    team_row = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).first()
    assert team_row is not None

    wr_one = create_player_with_position(client, name="Auto Flex WR One", position="WR")
    wr_two = create_player_with_position(client, name="Auto Flex WR Two", position="WR")
    wr_overflow = create_player_with_position(client, name="Auto Flex WR Overflow", position="WR")

    db_session.add_all(
        [
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=wr_one, slot="WR1", status="active"),
            RosterEntry(league_id=league["id"], team_id=team_row.id, player_id=wr_two, slot="WR2", status="active"),
        ]
    )
    db_session.commit()

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)

    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=95)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()

    league_row = db_session.query(League).filter(League.id == league["id"]).first()
    assert league_row is not None
    changed = league_routes._autopick_timed_out_current_team(
        db_session,
        league=league_row,
        current_user=None,
    )
    assert changed is True
    db_session.commit()

    overflow_entry = (
        db_session.query(RosterEntry)
        .filter(
            RosterEntry.league_id == league["id"],
            RosterEntry.team_id == team_row.id,
            RosterEntry.player_id == wr_overflow,
        )
        .first()
    )
    assert overflow_entry is not None
    assert overflow_entry.slot == "FLEX"

def test_draft_player_pool_import_requires_commissioner(client):
    owner_token = create_user_and_token(client, "owner-import")
    member_token = create_user_and_token(client, "member-import")
    league = create_league(client, owner_token)
    join_response = client.post(
        f"/leagues/{league['id']}/join",
        headers=auth_headers(member_token),
    )
    assert join_response.status_code == 200

    response = client.post(
        f"/leagues/{league['id']}/draft-room/player-pool/import",
        json={
            "replace_mode": "upsert",
            "rows": [
                {"name": "Quinn Ewers", "position": "QB", "school": "Texas"},
            ],
        },
        headers=auth_headers(member_token),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "commissioner only"


def test_draft_player_pool_import_upsert_and_replace(client):
    token = create_user_and_token(client, "pool-owner")
    league = create_league(client, token)

    seed_response = client.post(
        "/players",
        json=[
            {
                "external_id": "legacy-1",
                "name": "Legacy Runner",
                "position": "RB",
                "school": "Legacy U",
                "image_url": None,
            }
        ],
    )
    assert seed_response.status_code == 201

    import_response = client.post(
        f"/leagues/{league['id']}/draft-room/player-pool/import",
        json={
            "replace_mode": "replace_offense_pool",
            "rows": [
                {
                    "external_id": "2026-qb-1",
                    "name": "Quinn Ewers",
                    "position": "QB",
                    "school": "Texas",
                },
                {
                    "external_id": "2026-rb-1",
                    "name": "CJ Baxter",
                    "position": "RB",
                    "school": "Texas",
                },
            ],
        },
        headers=auth_headers(token),
    )
    assert import_response.status_code == 200
    body = import_response.json()
    assert body["received"] == 2
    assert body["created"] >= 2
    assert body["removed"] >= 1


def test_draft_pick_idempotency_key_replays_without_duplicate_pick(client, db_session):
    token = create_user_and_token(client, "idem")
    league = create_league(client, token)
    player_one_id = create_player(client, "Idempotent QB")
    player_two_id = create_player(client, "Different QB")
    headers = auth_headers(token) | {"Idempotency-Key": "pick-abc-123"}
    force_draft_live(db_session, league_id=league["id"])

    first_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_one_id},
        headers=headers,
    )
    assert first_response.status_code == 201
    first_room = first_response.json()
    assert len(first_room["picks"]) == 1

    replay_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_one_id},
        headers=headers,
    )
    assert replay_response.status_code == 201
    replay_room = replay_response.json()
    assert len(replay_room["picks"]) == 1
    assert replay_room["picks"][0]["player_id"] == player_one_id

    conflict_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_two_id},
        headers=headers,
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == "Idempotency key already used with a different player."


def test_draft_room_snapshot_returns_event_stream_delta(client, db_session):
    token = create_user_and_token(client, "snapshot")
    league = create_league(client, token)
    player_id = create_player(client, "Snapshot QB")
    force_draft_live(db_session, league_id=league["id"])

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token) | {"Idempotency-Key": "snapshot-pick-1"},
    )
    assert pick_response.status_code == 201

    snapshot_response = client.get(
        f"/leagues/{league['id']}/draft-room/snapshot",
        params={"since_seq": 0, "limit": 250},
        headers=auth_headers(token),
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["latest_seq"] >= 1
    assert snapshot["draft_room"]["server_state_seq"] == snapshot["latest_seq"]
    assert isinstance(snapshot["events"], list)
    assert any(event["event_type"] == "draft.pick.made" for event in snapshot["events"])

    delta_response = client.get(
        f"/leagues/{league['id']}/draft-room/snapshot",
        params={"since_seq": snapshot["latest_seq"], "limit": 250},
        headers=auth_headers(token),
    )
    assert delta_response.status_code == 200
    delta = delta_response.json()
    assert delta["events"] == []


def test_league_events_endpoint_returns_cursorable_event_log(client, db_session):
    token = create_user_and_token(client, "events")
    league = create_league(client, token)
    player_id = create_player(client, "Events QB")
    force_draft_live(db_session, league_id=league["id"])

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token) | {"Idempotency-Key": "events-pick-1"},
    )
    assert pick_response.status_code == 201

    events_response = client.get(
        f"/leagues/{league['id']}/events",
        params={"since_seq": 0, "limit": 250},
        headers=auth_headers(token),
    )
    assert events_response.status_code == 200
    payload = events_response.json()
    assert payload["latest_seq"] >= 1
    assert any(row["event_type"] == "draft.pick.made" for row in payload["data"])

    latest_seq = payload["latest_seq"]
    delta_response = client.get(
        f"/leagues/{league['id']}/events",
        params={"since_seq": latest_seq, "limit": 250},
        headers=auth_headers(token),
    )
    assert delta_response.status_code == 200
    assert delta_response.json()["data"] == []
