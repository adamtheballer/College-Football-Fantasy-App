from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from conftest import TestingSessionLocal, admin_headers
import pytest
from sqlalchemy.exc import IntegrityError

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.services.league_weeks import current_cfb_week_state
from collegefootballfantasy_api.app.services import waiver_service


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == f"coach-{suffix}@example.com").one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return response.json()["access_token"]


def parse_api_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def create_league(client, token: str, waiver_type: str = "faab", waiver_period_hours: int = 24) -> dict:
    payload = {
        "basics": {
            "name": "Roster League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": "Roster league",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BENCH": 4, "IR": 1},
            "playoff_teams": 4,
            "waiver_type": waiver_type,
            "waiver_period_hours": waiver_period_hours,
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
    response = client.post("/leagues", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()["league"]


def create_players(client) -> tuple[int, int]:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": "Runner One",
                "position": "RB",
                "school": "Texas",
                "image_url": None,
            },
            {
                "external_id": None,
                "name": "Runner Two",
                "position": "RB",
                "school": "Oregon",
                "image_url": None,
            },
        ],
        headers=admin_headers(client),
    )
    assert response.status_code == 201
    rows = response.json()
    return rows[0]["id"], rows[1]["id"]


def create_position_players(client) -> dict[str, int]:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": "Pocket Passer",
                "position": "QB",
                "school": "Texas",
                "image_url": None,
            },
            {
                "external_id": None,
                "name": "Place Kicker",
                "position": "K",
                "school": "Oregon",
                "image_url": None,
            },
        ],
        headers=admin_headers(client),
    )
    assert response.status_code == 201
    return {row["position"]: row["id"] for row in response.json()}


def test_team_and_roster_routes_require_membership_and_ownership(client, db_session):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    player_id, _ = create_players(client)

    team_list_response = client.get(f"/leagues/{league['id']}/teams", headers=auth_headers(outsider_token))
    assert team_list_response.status_code == 403

    roster_list_response = client.get(f"/teams/{team.id}/roster", headers=auth_headers(outsider_token))
    assert roster_list_response.status_code == 403

    add_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(outsider_token),
    )
    assert add_response.status_code == 403
    assert add_response.json()["detail"] == "league membership required"


def test_add_drop_lineup_and_transactions_workflow(client, db_session):
    token = create_user_and_token(client, "owner")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    team = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_name == "Coachowner").one()
    assert team is not None
    add_player_id, swap_player_id = create_players(client)

    add_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": add_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(token),
    )
    assert add_response.status_code == 201
    added_entry = add_response.json()

    lineup_response = client.patch(
        f"/teams/{team.id}/lineup",
        json={"assignments": [{"roster_entry_id": added_entry["id"], "slot": "BENCH"}]},
        headers=auth_headers(token),
    )
    assert lineup_response.status_code == 200
    assert lineup_response.json()["data"][0]["slot"] == "BENCH"

    add_drop_response = client.post(
        f"/teams/{team.id}/add-drop",
        json={"add_player_id": swap_player_id, "drop_roster_entry_id": added_entry["id"], "reason": "Waiver upgrade"},
        headers=auth_headers(token),
    )
    assert add_drop_response.status_code == 201
    body = add_drop_response.json()
    assert body["transaction"]["transaction_type"] == "add_drop"
    assert body["transaction"]["player_id"] == swap_player_id
    assert body["transaction"]["related_player_id"] == add_player_id
    assert body["roster"][0]["player"]["id"] == swap_player_id

    transaction_response = client.get(
        f"/leagues/{league['id']}/transactions",
        headers=auth_headers(token),
    )
    assert transaction_response.status_code == 200
    types = [row["transaction_type"] for row in transaction_response.json()["data"]]
    assert "add" in types
    assert "lineup" in types
    assert "add_drop" in types


def test_lineup_swap_updates_both_roster_entries_atomically(client, db_session):
    token = create_user_and_token(client, "atomic-lineup-swap")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    starter_player_id, bench_player_id = create_players(client)

    starter_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": starter_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(token),
    )
    bench_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": bench_player_id, "slot": "BENCH", "status": "active"},
        headers=auth_headers(token),
    )
    assert starter_response.status_code == 201
    assert bench_response.status_code == 201

    swap_response = client.patch(
        f"/teams/{team.id}/lineup",
        json={
            "assignments": [
                {"roster_entry_id": starter_response.json()["id"], "slot": "BENCH"},
                {"roster_entry_id": bench_response.json()["id"], "slot": "RB"},
            ]
        },
        headers=auth_headers(token),
    )

    assert swap_response.status_code == 200
    slots_by_id = {entry["id"]: entry["slot"] for entry in swap_response.json()["data"]}
    assert slots_by_id[starter_response.json()["id"]] == "BENCH"
    assert slots_by_id[bench_response.json()["id"]] == "RB"

    db_session.expire_all()
    assert db_session.get(RosterEntry, starter_response.json()["id"]).slot == "BENCH"
    assert db_session.get(RosterEntry, bench_response.json()["id"]).slot == "RB"


def test_waiver_claim_contract_persists_and_processes_exact_drop_entry(client, db_session):
    token = create_user_and_token(client, "waiver-owner")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    drop_player_id, add_player_id = create_players(client)

    roster_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": drop_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 201
    drop_entry_id = roster_response.json()["id"]

    submitted_at = datetime.now(timezone.utc)
    submit_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={
            "team_id": team.id,
            "add_player_id": add_player_id,
            "drop_roster_entry_id": drop_entry_id,
            "faab_bid": 7,
            "reason": "Upgrade",
        },
        headers=auth_headers(token),
    )

    assert submit_response.status_code == 201
    body = submit_response.json()
    assert body["team_id"] == team.id
    assert body["fantasy_team_id"] == team.id
    assert body["add_player_id"] == add_player_id
    assert body["drop_roster_entry_id"] == drop_entry_id
    assert body["drop_player_id"] == drop_player_id
    assert body["faab_bid"] == 7
    assert body["process_after"] is not None
    process_after = parse_api_datetime(body["process_after"])
    settings = db_session.query(LeagueSettings).filter_by(league_id=league["id"]).one()
    assert settings.next_waiver_run_at is not None
    assert settings.waiver_process_hour == 8
    assert process_after == parse_api_datetime(settings.next_waiver_run_at.isoformat())
    assert process_after.astimezone(ZoneInfo("America/Los_Angeles")).hour == 8
    assert process_after > submitted_at

    list_response = client.get(f"/leagues/{league['id']}/waivers", headers=auth_headers(token))
    assert list_response.status_code == 200
    assert any(claim["id"] == body["id"] for claim in list_response.json()["claims"])

    immediate_process_response = client.post(f"/leagues/{league['id']}/waivers/process", headers=auth_headers(token))
    assert immediate_process_response.status_code == 200
    assert immediate_process_response.json() == {"processed": 0, "failed": 0, "pending": 1}
    assert db_session.query(RosterEntry).filter_by(id=drop_entry_id, player_id=drop_player_id).one()

    claim = db_session.get(WaiverClaim, body["id"])
    claim.process_after = datetime.now(timezone.utc) + timedelta(days=1)
    db_session.commit()

    not_due_response = client.post(f"/leagues/{league['id']}/waivers/process", headers=auth_headers(token))
    assert not_due_response.status_code == 200
    assert not_due_response.json() == {"processed": 0, "failed": 0, "pending": 1}
    assert db_session.query(RosterEntry).filter_by(id=drop_entry_id, player_id=drop_player_id).one()

    claim.process_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    due_response = client.post(f"/leagues/{league['id']}/waivers/process", headers=auth_headers(token))
    assert due_response.status_code == 200
    assert due_response.json() == {"processed": 1, "failed": 0, "pending": 0}
    db_session.expire_all()
    assert db_session.query(RosterEntry).filter_by(team_id=team.id, player_id=drop_player_id).first() is None
    assert db_session.query(RosterEntry).filter_by(team_id=team.id, player_id=add_player_id).one()
    assert db_session.get(WaiverClaim, body["id"]).status == "processed"


def test_waiver_claim_uses_configured_waiver_period_hours(client, db_session):
    token = create_user_and_token(client, "waiver-window")
    league = create_league(client, token, waiver_period_hours=48)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    _drop_player_id, add_player_id = create_players(client)

    submitted_at = datetime.now(timezone.utc)
    submit_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player_id, "faab_bid": 0},
        headers=auth_headers(token),
    )

    assert submit_response.status_code == 201
    process_after = parse_api_datetime(submit_response.json()["process_after"])
    assert process_after > submitted_at
    settings = db_session.query(LeagueSettings).filter_by(league_id=league["id"]).one()
    assert settings.next_waiver_run_at is not None
    assert process_after == parse_api_datetime(settings.next_waiver_run_at.isoformat())

    process_response = client.post(f"/leagues/{league['id']}/waivers/process", headers=auth_headers(token))
    assert process_response.status_code == 200
    assert process_response.json() == {"processed": 0, "failed": 0, "pending": 1}


def test_waiver_claim_allows_same_day_before_player_school_kickoff(client, db_session, monkeypatch):
    fixed_now = datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(waiver_service, "_now", lambda: fixed_now)
    token = create_user_and_token(client, "waiver-before-kick")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    _drop_player_id, add_player_id = create_players(client)
    db_session.add(
        Game(
            season=2026,
            week=1,
            season_type="regular",
            start_date=fixed_now + timedelta(hours=2),
            home_team="Oregon",
            away_team="Other",
        )
    )
    db_session.commit()

    response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player_id, "faab_bid": 0},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert parse_api_datetime(response.json()["process_after"]) > fixed_now


def test_waiver_claim_rejects_player_school_after_kickoff(client, db_session, monkeypatch):
    fixed_now = datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(waiver_service, "_now", lambda: fixed_now)
    token = create_user_and_token(client, "waiver-after-kick")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    _drop_player_id, add_player_id = create_players(client)
    db_session.add(
        Game(
            season=2026,
            week=1,
            season_type="regular",
            start_date=fixed_now - timedelta(hours=2),
            home_team="Oregon",
            away_team="Other",
        )
    )
    db_session.commit()

    response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player_id, "faab_bid": 0},
        headers=auth_headers(token),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "waiver moves are locked after kickoff for: Oregon"


def test_waiver_claim_cancel_endpoint_marks_pending_claim_cancelled(client, db_session):
    token = create_user_and_token(client, "waiver-cancel")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    _drop_player_id, add_player_id = create_players(client)

    submit_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player_id, "faab_bid": 0},
        headers=auth_headers(token),
    )
    assert submit_response.status_code == 201
    claim_id = submit_response.json()["id"]

    cancel_response = client.post(
        f"/leagues/{league['id']}/waivers/claims/{claim_id}/cancel",
        json={"reason": "Changed plan"},
        headers=auth_headers(token),
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["id"] == claim_id
    assert cancel_response.json()["status"] == "cancelled"
    db_session.expire_all()
    assert db_session.get(WaiverClaim, claim_id).status == "cancelled"


def test_waiver_claim_rejects_payload_team_mismatch(client, db_session):
    owner_token = create_user_and_token(client, "waiver-owner-mismatch")
    member_token = create_user_and_token(client, "waiver-member-mismatch")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200
    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    owner_team = next(team for team in teams if team.owner_name == "Coachwaiver-owner-mismatch")
    member_team = next(team for team in teams if team.owner_name == "Coachwaiver-member-mismatch")
    _drop_player_id, add_player_id = create_players(client)

    response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": member_team.id, "add_player_id": add_player_id, "faab_bid": 0},
        headers=auth_headers(owner_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "waiver claim team does not match owned team"
    assert owner_team.id != member_team.id


def test_waiver_processing_deducts_faab_and_requires_commissioner(client, db_session):
    owner_token = create_user_and_token(client, "waiver-faab-owner")
    member_token = create_user_and_token(client, "waiver-faab-member")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200
    team = (
        db_session.query(Team)
        .filter(Team.league_id == league["id"], Team.owner_name == "Coachwaiver-faab-owner")
        .one()
    )
    _drop_player_id, add_player_id = create_players(client)

    submit_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player_id, "faab_bid": 9},
        headers=auth_headers(owner_token),
    )
    assert submit_response.status_code == 201
    claim = db_session.get(WaiverClaim, submit_response.json()["id"])
    claim.process_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    forbidden_response = client.post(
        f"/leagues/{league['id']}/waivers/process",
        headers=auth_headers(member_token),
    )
    assert forbidden_response.status_code == 403

    process_response = client.post(
        f"/leagues/{league['id']}/waivers/process",
        headers=auth_headers(owner_token),
    )
    assert process_response.status_code == 200
    assert process_response.json() == {"processed": 1, "failed": 0, "pending": 0}
    db_session.expire_all()
    priority = db_session.query(WaiverPriority).filter_by(league_id=league["id"], team_id=team.id).one()
    assert priority.faab_spent == 9
    assert priority.faab_remaining == 91


def test_waiver_priority_processing_moves_winner_to_bottom(client, db_session):
    owner_token = create_user_and_token(client, "waiver-priority-owner")
    member_token = create_user_and_token(client, "waiver-priority-member")
    league = create_league(client, owner_token, waiver_type="rolling")
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200
    team = (
        db_session.query(Team)
        .filter(Team.league_id == league["id"], Team.owner_name == "Coachwaiver-priority-owner")
        .one()
    )
    _drop_player_id, add_player_id = create_players(client)

    submit_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player_id, "faab_bid": 0},
        headers=auth_headers(owner_token),
    )
    assert submit_response.status_code == 201
    claim = db_session.get(WaiverClaim, submit_response.json()["id"])
    claim.process_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    process_response = client.post(
        f"/leagues/{league['id']}/waivers/process",
        headers=auth_headers(owner_token),
    )
    assert process_response.status_code == 200
    assert process_response.json() == {"processed": 1, "failed": 0, "pending": 0}
    db_session.expire_all()
    priorities = db_session.query(WaiverPriority).filter_by(league_id=league["id"]).all()
    assert len(priorities) == 2
    winner = next(priority for priority in priorities if priority.team_id == team.id)
    assert winner.priority == max(priority.priority for priority in priorities)


def test_waiver_locked_drop_player_is_rejected_after_kickoff(client, db_session):
    token = create_user_and_token(client, "waiver-locked-drop")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    drop_player_id, add_player_id = create_players(client)
    roster_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": drop_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 201
    drop_entry_id = roster_response.json()["id"]
    week_state = current_cfb_week_state(2026, now=datetime.now(timezone.utc), timezone_name="America/Los_Angeles")
    db_session.add(
        Game(
            external_id="waiver-locked-drop-game",
            season=2026,
            week=week_state.week,
            home_team="Texas",
            away_team="Oregon",
            start_date=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    submit_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={
            "team_id": team.id,
            "add_player_id": add_player_id,
            "drop_roster_entry_id": drop_entry_id,
            "faab_bid": 0,
        },
        headers=auth_headers(token),
    )
    assert submit_response.status_code == 409
    assert "locked after kickoff" in submit_response.json()["detail"]
    assert db_session.query(RosterEntry).filter_by(id=drop_entry_id, player_id=drop_player_id).one()


def test_waiver_claim_rejects_unavailable_add_player(client, db_session):
    owner_token = create_user_and_token(client, "waiver-unavailable-owner")
    member_token = create_user_and_token(client, "waiver-unavailable-member")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200
    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    owner_team = next(team for team in teams if team.owner_name == "Coachwaiver-unavailable-owner")
    member_team = next(team for team in teams if team.owner_name == "Coachwaiver-unavailable-member")
    add_player_id, _drop_player_id = create_players(client)
    roster_response = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": add_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert roster_response.status_code == 201

    response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": owner_team.id, "add_player_id": add_player_id, "faab_bid": 0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "player already on a league roster"


def test_roster_and_lineup_reject_position_ineligible_slots(client, db_session):
    token = create_user_and_token(client, "slot-owner")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    player_ids = create_position_players(client)

    bad_add_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": player_ids["K"], "slot": "QB", "status": "active"},
        headers=auth_headers(token),
    )
    assert bad_add_response.status_code == 409
    assert bad_add_response.json()["detail"] == "K is not eligible for QB"

    add_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": player_ids["QB"], "slot": "QB", "status": "active"},
        headers=auth_headers(token),
    )
    assert add_response.status_code == 201
    added_entry = add_response.json()

    bad_lineup_response = client.patch(
        f"/teams/{team.id}/lineup",
        json={"assignments": [{"roster_entry_id": added_entry["id"], "slot": "K"}]},
        headers=auth_headers(token),
    )
    assert bad_lineup_response.status_code == 409
    assert bad_lineup_response.json()["detail"] == "QB is not eligible for K"


def test_lineup_move_is_allowed_before_kickoff_then_locked_after_kickoff(client, db_session):
    token = create_user_and_token(client, "lineup-kickoff-lock")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    player_id, _ = create_players(client)
    roster_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 201
    roster_entry_id = roster_response.json()["id"]

    week_state = current_cfb_week_state(2026, now=datetime.now(timezone.utc), timezone_name="America/Los_Angeles")
    game = Game(
        external_id="lineup-kickoff-lock-game",
        season=2026,
        week=week_state.week,
        home_team="Texas",
        away_team="Oregon",
        start_date=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(game)
    db_session.commit()

    before_kickoff_response = client.patch(
        f"/teams/{team.id}/lineup",
        json={"assignments": [{"roster_entry_id": roster_entry_id, "slot": "BENCH"}]},
        headers=auth_headers(token),
    )
    assert before_kickoff_response.status_code == 200

    game.start_date = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    after_kickoff_response = client.patch(
        f"/teams/{team.id}/lineup",
        json={"assignments": [{"roster_entry_id": roster_entry_id, "slot": "RB"}]},
        headers=auth_headers(token),
    )
    assert after_kickoff_response.status_code == 409
    assert after_kickoff_response.json()["detail"] == "lineup changes are locked after kickoff for: Runner One"

    db_session.expire_all()
    assert db_session.get(RosterEntry, roster_entry_id).slot == "BENCH"
    roster_tab_response = client.get(f"/leagues/{league['id']}/roster", headers=auth_headers(token))
    assert roster_tab_response.status_code == 200
    locked_player = next(row for row in roster_tab_response.json()["roster"] if row["id"] == roster_entry_id)
    assert locked_player["is_locked"] is True
    assert locked_player["game_start_at"] is not None


def test_direct_drop_is_rejected_after_kickoff(client, db_session):
    token = create_user_and_token(client, "drop-kickoff-lock")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    player_id, _ = create_players(client)
    roster_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 201
    roster_entry_id = roster_response.json()["id"]

    week_state = current_cfb_week_state(2026, now=datetime.now(timezone.utc), timezone_name="America/Los_Angeles")
    db_session.add(
        Game(
            external_id="drop-kickoff-lock-game",
            season=2026,
            week=week_state.week,
            home_team="Texas",
            away_team="Oregon",
            start_date=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    response = client.delete(f"/teams/{team.id}/roster/{roster_entry_id}", headers=auth_headers(token))

    assert response.status_code == 409
    assert response.json()["detail"] == "player cannot be dropped after kickoff"
    assert db_session.get(RosterEntry, roster_entry_id) is not None


def test_add_drop_uses_open_flex_slot_when_primary_position_is_full(client, db_session):
    token = create_user_and_token(client, "add-drop-flex")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    settings = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).one()
    settings.roster_slots_json = {"QB": 0, "RB": 2, "WR": 0, "TE": 0, "FLEX": 1, "K": 1, "BENCH": 0}
    db_session.commit()

    players = [
        Player(name=f"Flex Runner {index}", position="RB", school="Texas") for index in range(1, 4)
    ] + [Player(name="Flex Kicker", position="K", school="Oregon")]
    db_session.add_all(players)
    db_session.commit()

    for player in players[:2]:
        response = client.post(
            f"/teams/{team.id}/roster",
            json={"player_id": player.id, "slot": "RB", "status": "active"},
            headers=auth_headers(token),
        )
        assert response.status_code == 201
    kicker_response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": players[3].id, "slot": "K", "status": "active"},
        headers=auth_headers(token),
    )
    assert kicker_response.status_code == 201

    response = client.post(
        f"/teams/{team.id}/add-drop",
        json={
            "add_player_id": players[2].id,
            "drop_roster_entry_id": kicker_response.json()["id"],
            "reason": "Need RB depth",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    added_entry = next(entry for entry in response.json()["roster"] if entry["player_id"] == players[2].id)
    assert added_entry["slot"] == "FLEX"


def test_superflex_slot_is_legal_when_it_is_configured(client, db_session):
    token = create_user_and_token(client, "configured-superflex")
    league = create_league(client, token)
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    settings = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).one()
    settings.roster_slots_json = {"QB": 1, "RB": 0, "WR": 0, "TE": 0, "FLEX": 0, "SUPERFLEX": 1, "K": 0, "BENCH": 0}
    settings.superflex_enabled = False
    qb = Player(name="Configured Superflex QB", position="QB", school="Texas")
    db_session.add(qb)
    db_session.commit()

    response = client.post(
        f"/teams/{team.id}/roster",
        json={"player_id": qb.id, "slot": "SUPERFLEX", "status": "active"},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["slot"] == "SUPERFLEX"


def test_team_and_roster_db_constraints_enforce_league_invariants(client, db_session):
    owner_token = create_user_and_token(client, "owner")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    owner_team, member_team = teams

    db_session.add(
        Team(
            league_id=league["id"],
            name="Duplicate Owner Team",
            owner_name=owner_team.owner_name,
            owner_user_id=owner_team.owner_user_id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    player_id, _ = create_players(client)
    db_session.add(
        RosterEntry(
            league_id=league["id"],
            team_id=owner_team.id,
            player_id=player_id,
            slot="RB",
            status="active",
        )
    )
    db_session.commit()

    db_session.add(
        RosterEntry(
            league_id=league["id"],
            team_id=member_team.id,
            player_id=player_id,
            slot="RB",
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
