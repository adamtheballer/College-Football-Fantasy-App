from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


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


def create_league(
    client,
    token: str,
    name: str = "Test League",
    draft_order_strategy: str = "fixed",
    is_private: bool = False,
) -> dict:
    payload = {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": 12,
            "is_private": is_private,
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
            "order_strategy": draft_order_strategy,
        },
    }
    response = client.post(
        "/leagues",
        json=payload,
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def test_create_and_list_leagues(client):
    token = create_user_and_token(client)
    created = create_league(client, token)

    response = client.get("/leagues", headers=auth_headers(token))
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
            "is_private": False,
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
    response = client.post("/leagues/create", json=payload, headers=auth_headers(token))
    assert response.status_code == 201


def test_create_league_persists_draft_order_strategy_meta(client, db_session):
    token = create_user_and_token(client, "draft-order")
    league = create_league(
        client,
        token,
        name="Random Order League",
        draft_order_strategy="random",
    )

    settings_row = (
        db_session.query(LeagueSettings)
        .filter(LeagueSettings.league_id == league["id"])
        .first()
    )
    assert settings_row is not None
    meta = settings_row.scoring_json.get("__meta__", {})
    assert meta.get("draft_order_strategy") == "random"


def test_league_detail_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(f"/leagues/{league['id']}", headers=auth_headers(outsider_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_league_members_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(f"/leagues/{league['id']}/members", headers=auth_headers(outsider_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_delete_league_requires_commissioner(client):
    commissioner_token = create_user_and_token(client, "commissioner")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, commissioner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    response = client.delete(f"/leagues/{league['id']}", headers=auth_headers(member_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "commissioner only"


def test_private_league_requires_invite_code_join_flow(client):
    owner_token = create_user_and_token(client, "private-owner")
    member_token = create_user_and_token(client, "private-member")
    league = create_league(client, owner_token, is_private=True)

    direct_join = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert direct_join.status_code == 403
    assert direct_join.json()["detail"] == "private leagues require an invite code"

    preview = client.post(
        "/leagues/join-by-code",
        json={"invite_code": league["invite_code"]},
    )
    assert preview.status_code == 200
    assert preview.json()["id"] == league["id"]

    invite_join = client.post(
        "/leagues/join-with-code",
        json={"invite_code": league["invite_code"]},
        headers=auth_headers(member_token),
    )
    assert invite_join.status_code == 200
    assert len(invite_join.json()["members"]) == 2


def test_league_workspace_returns_real_matchup_and_standings(client, db_session):
    token = create_user_and_token(client, "workspace")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
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
        headers=auth_headers(token),
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
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_league_hub_endpoints_return_scoreboard_rankings_and_news(client, db_session):
    commissioner_token = create_user_and_token(client, "comm")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, commissioner_token, name="Hub League")
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    commissioner_team, member_team = teams

    player = Player(name="Sam Test", position="QB", school="Alabama")
    db_session.add(player)
    db_session.flush()

    db_session.add(
        RosterEntry(
            league_id=league["id"],
            team_id=commissioner_team.id,
            player_id=player.id,
            slot="QB",
            status="active",
        )
    )
    db_session.add(
        Matchup(
            league_id=league["id"],
            season=2026,
            week=4,
            home_team_id=commissioner_team.id,
            away_team_id=member_team.id,
            status="live",
            home_score=128.5,
            away_score=120.1,
        )
    )
    db_session.add_all(
        [
            Standing(
                league_id=league["id"],
                team_id=commissioner_team.id,
                season=2026,
                week=4,
                wins=3,
                losses=0,
                ties=0,
                points_for=372.6,
                points_against=320.0,
            ),
            Standing(
                league_id=league["id"],
                team_id=member_team.id,
                season=2026,
                week=4,
                wins=1,
                losses=2,
                ties=0,
                points_for=298.4,
                points_against=325.7,
            ),
        ]
    )
    db_session.add(
        Transaction(
            league_id=league["id"],
            team_id=commissioner_team.id,
            transaction_type="add",
            player_id=player.id,
            created_by_user_id=league["commissioner_user_id"],
            reason="Waiver claim",
        )
    )
    db_session.add(
        Injury(
            player_id=player.id,
            season=2026,
            week=4,
            status="QUESTIONABLE",
            injury="Shoulder",
            return_timeline="Day-to-day",
        )
    )
    db_session.commit()

    matchup_response = client.get(
        f"/leagues/{league['id']}/matchups",
        headers=auth_headers(commissioner_token),
    )
    assert matchup_response.status_code == 200
    matchup_body = matchup_response.json()
    assert matchup_body["total"] == 1
    assert matchup_body["data"][0]["week"] == 4
    assert matchup_body["data"][0]["home_team_name"] == commissioner_team.name

    rankings_response = client.get(
        f"/leagues/{league['id']}/power-rankings",
        headers=auth_headers(commissioner_token),
    )
    assert rankings_response.status_code == 200
    rankings_body = rankings_response.json()
    assert rankings_body["total"] == 2
    assert rankings_body["data"][0]["team_id"] == commissioner_team.id
    assert rankings_body["data"][0]["rank"] == 1

    news_response = client.get(
        f"/leagues/{league['id']}/news",
        headers=auth_headers(commissioner_token),
    )
    assert news_response.status_code == 200
    news_body = news_response.json()
    assert news_body["total"] >= 2
    assert any(item["transaction_type"] == "add" for item in news_body["data"])
    assert any(item["transaction_type"] == "injury" for item in news_body["data"])


def test_league_hub_endpoints_require_membership(client):
    owner_token = create_user_and_token(client, "owner-hub")
    outsider_token = create_user_and_token(client, "outsider-hub")
    league = create_league(client, owner_token, name="Protected Hub League")

    for path in ("matchups", "power-rankings", "news"):
        response = client.get(f"/leagues/{league['id']}/{path}", headers=auth_headers(outsider_token))
        assert response.status_code == 403
        assert response.json()["detail"] == "league membership required"


def test_matchmaking_join_starts_two_minute_draft_when_full(client, db_session):
    tokens = [create_user_and_token(client, f"matchmake-{index}") for index in range(4)]
    responses = []
    for token in tokens:
        response = client.post(
            "/leagues/matchmaking/join",
            json={"team_count": 4, "skill_mode": "beginner"},
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        responses.append(response.json())

    league_ids = {payload["id"] for payload in responses}
    assert len(league_ids) == 1

    final_payload = responses[-1]
    assert final_payload["status"] == "draft_scheduled"
    assert final_payload["draft"] is not None

    draft_start = datetime.fromisoformat(
        final_payload["draft"]["draft_datetime_utc"].replace("Z", "+00:00")
    )
    if draft_start.tzinfo is None:
        draft_start = draft_start.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    assert now + timedelta(seconds=30) <= draft_start <= now + timedelta(minutes=3)

    settings_row = (
        db_session.query(LeagueSettings)
        .filter(LeagueSettings.league_id == final_payload["id"])
        .first()
    )
    assert settings_row is not None

    meta = settings_row.scoring_json.get("__meta__", {})
    assert meta.get("draft_order_strategy") == "random"
    order_ids = meta.get("draft_order_team_ids")
    assert isinstance(order_ids, list)
    assert len(order_ids) == 4
    assert len(set(order_ids)) == 4


def test_matchmaking_join_rejects_invalid_team_count(client):
    token = create_user_and_token(client, "matchmake-invalid")
    response = client.post(
        "/leagues/matchmaking/join",
        json={"team_count": 5, "skill_mode": "pro"},
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert "team_count must be one of" in response.json()["detail"]


def test_league_week_state_lifecycle_transitions(client):
    token = create_user_and_token(client, "week-state")
    league = create_league(client, token)

    get_response = client.get(
        f"/leagues/{league['id']}/weeks/2026/1",
        headers=auth_headers(token),
    )
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "open"

    lock_response = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/status",
        json={"status": "locked"},
        headers=auth_headers(token),
    )
    assert lock_response.status_code == 200
    assert lock_response.json()["status"] == "locked"

    finalize_response = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/status",
        json={"status": "finalized"},
        headers=auth_headers(token),
    )
    assert finalize_response.status_code == 200
    assert finalize_response.json()["status"] == "finalized"

    corrected_response = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/status",
        json={"status": "corrected"},
        headers=auth_headers(token),
    )
    assert corrected_response.status_code == 200
    assert corrected_response.json()["status"] == "corrected"


def test_finalize_week_persists_standings_snapshot(client, db_session):
    commissioner_token = create_user_and_token(client, "finalize-comm")
    member_token = create_user_and_token(client, "finalize-member")
    league = create_league(client, commissioner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    home_team, away_team = teams

    db_session.add(
        Matchup(
            league_id=league["id"],
            season=2026,
            week=1,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            status="final",
            home_score=131.2,
            away_score=125.4,
        )
    )
    db_session.commit()

    finalize_response = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/finalize",
        headers=auth_headers(commissioner_token),
    )
    assert finalize_response.status_code == 200
    body = finalize_response.json()
    assert body["status"] == "finalized"
    assert len(body["standings"]) == 2
    winner = next(row for row in body["standings"] if row["team_id"] == home_team.id)
    loser = next(row for row in body["standings"] if row["team_id"] == away_team.id)
    assert winner["wins"] == 1
    assert winner["losses"] == 0
    assert loser["wins"] == 0
    assert loser["losses"] == 1

    persisted_rows = (
        db_session.query(Standing)
        .filter(Standing.league_id == league["id"], Standing.season == 2026, Standing.week == 1)
        .all()
    )
    assert len(persisted_rows) == 2

    # Re-finalizing should be safe and idempotent.
    second_finalize = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/finalize",
        headers=auth_headers(commissioner_token),
    )
    assert second_finalize.status_code == 200
    assert second_finalize.json()["status"] == "finalized"


def test_finalize_week_rejects_non_final_matchups(client, db_session):
    token = create_user_and_token(client, "finalize-block")
    league = create_league(client, token)
    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 1

    # Create a second placeholder team to build a matchup.
    second_team = Team(
        league_id=league["id"],
        name="Blocked Team",
        owner_name=None,
        owner_user_id=None,
    )
    db_session.add(second_team)
    db_session.flush()

    db_session.add(
        Matchup(
            league_id=league["id"],
            season=2026,
            week=1,
            home_team_id=teams[0].id,
            away_team_id=second_team.id,
            status="live",
            home_score=10.0,
            away_score=9.5,
        )
    )
    db_session.commit()

    response = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/finalize",
        headers=auth_headers(token),
    )
    assert response.status_code == 409
    assert "not final" in response.json()["detail"]


def test_recompute_week_scores_updates_matchups_and_team_scores(client, db_session):
    commissioner_token = create_user_and_token(client, "score-comm")
    member_token = create_user_and_token(client, "score-member")
    league = create_league(client, commissioner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    team_one, team_two = teams

    players_response = client.post(
        "/players",
        json=[
            {"external_id": None, "name": "Score QB 1", "position": "QB", "school": "Texas", "image_url": None},
            {"external_id": None, "name": "Score RB 2", "position": "RB", "school": "USC", "image_url": None},
        ],
    )
    assert players_response.status_code == 201
    player_one_id = players_response.json()[0]["id"]
    player_two_id = players_response.json()[1]["id"]

    add_one = client.post(
        f"/teams/{team_one.id}/roster",
        json={"player_id": player_one_id, "slot": "QB", "status": "active"},
        headers=auth_headers(commissioner_token),
    )
    assert add_one.status_code == 201
    add_two = client.post(
        f"/teams/{team_two.id}/roster",
        json={"player_id": player_two_id, "slot": "RB", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_two.status_code == 201

    db_session.add_all(
        [
            WeeklyProjection(player_id=player_one_id, season=2026, week=1, fantasy_points=24.6),
            WeeklyProjection(player_id=player_two_id, season=2026, week=1, fantasy_points=18.2),
            Matchup(
                league_id=league["id"],
                season=2026,
                week=1,
                home_team_id=team_one.id,
                away_team_id=team_two.id,
                status="scheduled",
                home_score=0.0,
                away_score=0.0,
            ),
        ]
    )
    db_session.commit()

    recompute_response = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/scores/recompute",
        json={"source_mode": "projection_only", "finalize_matchups": False, "finalize_week": False},
        headers=auth_headers(commissioner_token),
    )
    assert recompute_response.status_code == 200
    body = recompute_response.json()
    assert body["week_state"] == "open"
    assert body["player_actual_points_used"] == 0
    assert body["player_projection_points_used"] == 2
    assert len(body["team_scores"]) == 2
    assert len(body["matchup_scores"]) == 1
    assert body["matchup_scores"][0]["status"] == "projected"

    db_session.expire_all()
    score_rows = (
        db_session.query(TeamWeekScore)
        .filter(TeamWeekScore.league_id == league["id"], TeamWeekScore.season == 2026, TeamWeekScore.week == 1)
        .all()
    )
    assert len(score_rows) == 2
    by_team = {row.team_id: row for row in score_rows}
    assert round(float(by_team[team_one.id].points_starters), 1) == 24.6
    assert round(float(by_team[team_two.id].points_starters), 1) == 18.2

    scoring_run = db_session.query(ScoringRun).order_by(ScoringRun.id.desc()).first()
    assert scoring_run is not None
    assert scoring_run.status == "completed"
    assert scoring_run.source_mode == "projection_only"


def test_recompute_can_finalize_and_correct_week_state(client, db_session):
    commissioner_token = create_user_and_token(client, "score-final-comm")
    member_token = create_user_and_token(client, "score-final-member")
    league = create_league(client, commissioner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    team_one, team_two = teams

    players_response = client.post(
        "/players",
        json=[
            {"external_id": None, "name": "Finalize QB", "position": "QB", "school": "Alabama", "image_url": None},
            {"external_id": None, "name": "Finalize WR", "position": "WR", "school": "LSU", "image_url": None},
        ],
    )
    assert players_response.status_code == 201
    player_one_id = players_response.json()[0]["id"]
    player_two_id = players_response.json()[1]["id"]

    add_one = client.post(
        f"/teams/{team_one.id}/roster",
        json={"player_id": player_one_id, "slot": "QB", "status": "active"},
        headers=auth_headers(commissioner_token),
    )
    assert add_one.status_code == 201
    add_two = client.post(
        f"/teams/{team_two.id}/roster",
        json={"player_id": player_two_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_two.status_code == 201

    db_session.add_all(
        [
            WeeklyProjection(player_id=player_one_id, season=2026, week=1, fantasy_points=31.0),
            WeeklyProjection(player_id=player_two_id, season=2026, week=1, fantasy_points=20.5),
            Matchup(
                league_id=league["id"],
                season=2026,
                week=1,
                home_team_id=team_one.id,
                away_team_id=team_two.id,
                status="scheduled",
                home_score=0.0,
                away_score=0.0,
            ),
        ]
    )
    db_session.commit()

    finalize_response = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/scores/recompute",
        json={"source_mode": "projection_only", "finalize_matchups": True, "finalize_week": True},
        headers=auth_headers(commissioner_token),
    )
    assert finalize_response.status_code == 200
    payload = finalize_response.json()
    assert payload["week_state"] == "finalized"
    assert payload["standings_count"] == 2
    assert payload["matchup_scores"][0]["status"] == "final"

    corrected_response = client.post(
        f"/leagues/{league['id']}/weeks/2026/1/scores/recompute",
        json={"source_mode": "projection_only", "finalize_matchups": True, "finalize_week": True},
        headers=auth_headers(commissioner_token),
    )
    assert corrected_response.status_code == 200
    corrected_payload = corrected_response.json()
    assert corrected_payload["week_state"] == "corrected"

    run_history_response = client.get(
        f"/leagues/{league['id']}/weeks/2026/1/scores/runs",
        headers=auth_headers(commissioner_token),
    )
    assert run_history_response.status_code == 200
    history = run_history_response.json()["data"]
    assert len(history) >= 2
    assert history[0]["status"] == "completed"
