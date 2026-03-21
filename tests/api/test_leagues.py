from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team


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
    return response.json()["user"]["api_token"]


def create_league(client, token: str, name: str = "Test League") -> dict:
    payload = {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": "Workspace league",
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
        headers={"X-User-Token": token},
    )
    assert response.status_code == 201
    return response.json()["league"]


def test_create_and_list_leagues(client):
    token = create_user_and_token(client)
    created = create_league(client, token)

    response = client.get("/leagues", headers={"X-User-Token": token})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["name"] == created["name"]
    assert data["data"][0]["max_teams"] == created["max_teams"]
    assert len(data["data"][0]["members"]) == 1
    assert data["data"][0]["draft"]["draft_type"] == "snake"


def test_legacy_create_alias_still_works(client):
    token = create_user_and_token(client)
    payload = {
        "basics": {
            "name": "Legacy League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": None,
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
    response = client.post("/leagues/create", json=payload, headers={"X-User-Token": token})
    assert response.status_code == 201


def test_league_detail_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(f"/leagues/{league['id']}", headers={"X-User-Token": outsider_token})
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_league_members_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(f"/leagues/{league['id']}/members", headers={"X-User-Token": outsider_token})
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_delete_league_requires_commissioner(client):
    commissioner_token = create_user_and_token(client, "commissioner")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, commissioner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers={"X-User-Token": member_token})
    assert join_response.status_code == 200

    response = client.delete(f"/leagues/{league['id']}", headers={"X-User-Token": member_token})
    assert response.status_code == 403
    assert response.json()["detail"] == "commissioner only"


def test_league_workspace_returns_real_matchup_and_standings(client, db_session):
    token = create_user_and_token(client, "workspace")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers={"X-User-Token": member_token})
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    commissioner_team, member_team = teams

    db_session.add(
        Matchup(
            league_id=league["id"],
            season=2026,
            week=3,
            home_team_id=commissioner_team.id,
            away_team_id=member_team.id,
            status="live",
            home_score=118.4,
            away_score=111.2,
        )
    )
    db_session.add_all(
        [
            Standing(
                league_id=league["id"],
                team_id=commissioner_team.id,
                season=2026,
                week=3,
                wins=2,
                losses=0,
                ties=0,
                points_for=244.7,
                points_against=196.0,
            ),
            Standing(
                league_id=league["id"],
                team_id=member_team.id,
                season=2026,
                week=3,
                wins=1,
                losses=1,
                ties=0,
                points_for=210.3,
                points_against=211.8,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league['id']}/workspace",
        headers={"X-User-Token": token},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["matchup_summary"]["week"] == 3
    assert body["matchup_summary"]["opponent_team_name"] == member_team.name
    assert body["matchup_summary"]["projected_points_for"] == 118.4
    assert body["standings_summary"][0]["team_id"] == commissioner_team.id
    assert body["standings_summary"][0]["wins"] == 2
    assert body["standings_summary"][1]["team_id"] == member_team.id


def test_league_workspace_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(
        f"/leagues/{league['id']}/workspace",
        headers={"X-User-Token": outsider_token},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"
