import pytest
from sqlalchemy.exc import IntegrityError

from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team


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
    )
    assert response.status_code == 201
    rows = response.json()
    return rows[0]["id"], rows[1]["id"]


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
