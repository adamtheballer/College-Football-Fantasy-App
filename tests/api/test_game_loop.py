from api.app.models.fantasy_player_score import FantasyPlayerScore
from api.app.models.lineup import Lineup, LineupEntry
from api.app.models.matchup import Matchup
from api.app.models.player import Player
from api.app.models.player_stat import PlayerStat
from api.app.models.roster import RosterEntry
from api.app.models.standing import Standing
from api.app.models.team import Team
from api.app.models.team_weekly_score import TeamWeeklyScore
from api.app.models.user import User
from api.app.services.scoring_service import calculate_player_fantasy_points


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, db_session, suffix: str) -> tuple[User, str]:
    email = f"game-loop-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={"first_name": f"Coach{suffix}", "email": email, "password": "secret123"},
    )
    assert response.status_code == 201
    user = db_session.query(User).filter(User.email == email).one()
    return user, response.json()["access_token"]


def create_league(client, token: str, name: str = "Game Loop League") -> dict:
    response = client.post(
        "/leagues",
        headers=auth_headers(token),
        json={
            "basics": {
                "name": name,
                "season_year": 2026,
                "max_teams": 12,
                "is_private": False,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 1, "RB": 1, "BENCH": 3},
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
                "order_strategy": "fixed",
            },
        },
    )
    assert response.status_code == 201
    return response.json()["league"]


def create_player(db_session, name: str, position: str) -> Player:
    player = Player(external_id=None, name=name, position=position, school="Test State", image_url=None)
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)
    return player


def setup_two_team_league(client, db_session):
    commissioner, commissioner_token = create_user_and_token(client, db_session, "commissioner")
    member, member_token = create_user_and_token(client, db_session, "member")
    league = create_league(client, commissioner_token)
    join = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join.status_code == 200
    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    return league, commissioner, commissioner_token, member, member_token, teams


def test_generate_schedule_requires_commissioner(client, db_session):
    league, _commissioner, _commissioner_token, _member, member_token, _teams = setup_two_team_league(client, db_session)
    response = client.post(
        f"/leagues/{league['id']}/schedule/generate",
        json={"weeks": 2},
        headers=auth_headers(member_token),
    )
    assert response.status_code == 403


def test_generate_schedule_requires_two_teams(client, db_session):
    _commissioner, commissioner_token = create_user_and_token(client, db_session, "solo")
    league = create_league(client, commissioner_token, "Solo League")
    response = client.post(
        f"/leagues/{league['id']}/schedule/generate",
        json={"weeks": 2},
        headers=auth_headers(commissioner_token),
    )
    assert response.status_code == 400


def test_generate_schedule_creates_matchups_and_prevents_duplicates(client, db_session):
    league, _commissioner, commissioner_token, _member, _member_token, _teams = setup_two_team_league(client, db_session)
    response = client.post(
        f"/leagues/{league['id']}/schedule/generate",
        json={"weeks": 3},
        headers=auth_headers(commissioner_token),
    )
    assert response.status_code == 200
    assert response.json()["created"] == 3

    duplicate = client.post(
        f"/leagues/{league['id']}/schedule/generate",
        json={"weeks": 3},
        headers=auth_headers(commissioner_token),
    )
    assert duplicate.status_code == 409


def test_generate_schedule_handles_odd_team_count(client, db_session):
    commissioner, commissioner_token = create_user_and_token(client, db_session, "odd-comm")
    member_one, member_one_token = create_user_and_token(client, db_session, "odd-one")
    member_two, member_two_token = create_user_and_token(client, db_session, "odd-two")
    league = create_league(client, commissioner_token, "Odd League")
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_one_token)).status_code == 200
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_two_token)).status_code == 200

    response = client.post(
        f"/leagues/{league['id']}/schedule/generate",
        json={"weeks": 3},
        headers=auth_headers(commissioner_token),
    )
    assert response.status_code == 200
    assert response.json()["created"] == 3


def test_get_or_create_lineup_from_roster(client, db_session):
    league, _commissioner, commissioner_token, _member, _member_token, teams = setup_two_team_league(client, db_session)
    player = create_player(db_session, "Snapshot QB", "QB")
    add = client.post(
        f"/teams/{teams[0].id}/roster",
        json={"player_id": player.id, "slot": "QB", "status": "active"},
        headers=auth_headers(commissioner_token),
    )
    assert add.status_code == 201

    response = client.get(
        f"/leagues/{league['id']}/teams/{teams[0].id}/lineup",
        params={"season": 2026, "week": 1},
        headers=auth_headers(commissioner_token),
    )
    assert response.status_code == 200
    assert response.json()["entries"][0]["player_id"] == player.id
    assert response.json()["entries"][0]["is_starter"] is True


def test_update_lineup_rejects_non_owner_non_rostered_duplicate_and_locked(client, db_session):
    league, _commissioner, commissioner_token, _member, member_token, teams = setup_two_team_league(client, db_session)
    player = create_player(db_session, "Lineup QB", "QB")
    outsider_player = create_player(db_session, "Not Rostered", "RB")
    add = client.post(
        f"/teams/{teams[0].id}/roster",
        json={"player_id": player.id, "slot": "QB", "status": "active"},
        headers=auth_headers(commissioner_token),
    )
    assert add.status_code == 201
    roster_entry_id = add.json()["id"]

    payload = {"assignments": [{"roster_entry_id": roster_entry_id, "player_id": player.id, "slot": "QB", "is_starter": True}]}
    assert client.patch(
        f"/leagues/{league['id']}/teams/{teams[0].id}/lineup",
        params={"season": 2026, "week": 1},
        json=payload,
        headers=auth_headers(member_token),
    ).status_code == 403

    bad_non_rostered = {"assignments": [{"player_id": outsider_player.id, "slot": "RB", "is_starter": True}]}
    assert client.patch(
        f"/leagues/{league['id']}/teams/{teams[0].id}/lineup",
        params={"season": 2026, "week": 1},
        json=bad_non_rostered,
        headers=auth_headers(commissioner_token),
    ).status_code == 409

    duplicate = {"assignments": [payload["assignments"][0], payload["assignments"][0]]}
    assert client.patch(
        f"/leagues/{league['id']}/teams/{teams[0].id}/lineup",
        params={"season": 2026, "week": 1},
        json=duplicate,
        headers=auth_headers(commissioner_token),
    ).status_code == 409

    assert client.post(
        f"/leagues/{league['id']}/teams/{teams[0].id}/lineup/lock",
        params={"season": 2026, "week": 1},
        headers=auth_headers(commissioner_token),
    ).status_code == 200
    assert client.patch(
        f"/leagues/{league['id']}/teams/{teams[0].id}/lineup",
        params={"season": 2026, "week": 1},
        json=payload,
        headers=auth_headers(commissioner_token),
    ).status_code == 409


def test_lineup_snapshot_survives_roster_change(client, db_session):
    league, _commissioner, commissioner_token, _member, _member_token, teams = setup_two_team_league(client, db_session)
    player = create_player(db_session, "Historical WR", "WR")
    add = client.post(
        f"/teams/{teams[0].id}/roster",
        json={"player_id": player.id, "slot": "BENCH", "status": "active"},
        headers=auth_headers(commissioner_token),
    )
    assert add.status_code == 201
    lineup = client.get(
        f"/leagues/{league['id']}/teams/{teams[0].id}/lineup",
        params={"season": 2026, "week": 1},
        headers=auth_headers(commissioner_token),
    )
    assert lineup.status_code == 200
    db_session.query(RosterEntry).filter(RosterEntry.id == add.json()["id"]).delete()
    db_session.commit()
    entry = db_session.query(LineupEntry).filter(LineupEntry.player_id == player.id).one()
    assert entry.player_id == player.id


def test_calculate_player_fantasy_points_defaults_and_missing_stats():
    points, breakdown = calculate_player_fantasy_points(
        {"passing_yards": 250, "passing_touchdowns": 2, "interceptions": 1},
        {},
    )
    assert points == 16.0
    assert breakdown["passing_yards"]["points"] == 10.0

    missing_points, _missing_breakdown = calculate_player_fantasy_points({"passing_yards": "bad"}, {})
    assert missing_points == 0.0


def test_score_and_finalize_week_are_idempotent_and_use_lineup_snapshots(client, db_session):
    league, _commissioner, commissioner_token, _member, member_token, teams = setup_two_team_league(client, db_session)
    home_qb = create_player(db_session, "Home QB", "QB")
    home_bench = create_player(db_session, "Home Bench", "RB")
    away_qb = create_player(db_session, "Away QB", "QB")
    for team, player, slot, token in [
        (teams[0], home_qb, "QB", commissioner_token),
        (teams[0], home_bench, "BENCH", commissioner_token),
        (teams[1], away_qb, "QB", member_token),
    ]:
        assert client.post(
            f"/teams/{team.id}/roster",
            json={"player_id": player.id, "slot": slot, "status": "active"},
            headers=auth_headers(token),
        ).status_code == 201

    db_session.add_all(
        [
            PlayerStat(player_id=home_qb.id, season=2026, week=1, stats={"passing_yards": 300, "passing_touchdowns": 2}),
            PlayerStat(player_id=home_bench.id, season=2026, week=1, stats={"rushing_yards": 100, "rushing_touchdowns": 1}),
            PlayerStat(player_id=away_qb.id, season=2026, week=1, stats={"passing_yards": 200}),
            Matchup(
                league_id=league["id"],
                season=2026,
                week=1,
                home_team_id=teams[0].id,
                away_team_id=teams[1].id,
                status="scheduled",
                home_score=0,
                away_score=0,
            ),
        ]
    )
    db_session.commit()

    score = client.post(
        f"/leagues/{league['id']}/weeks/1/score",
        headers=auth_headers(commissioner_token),
    )
    assert score.status_code == 200
    home_score = next(row for row in score.json()["team_scores"] if row["team_id"] == teams[0].id)
    assert home_score["starter_points"] == 20.0
    assert home_score["bench_points"] == 16.0
    assert score.json()["matchups"][0]["home_score"] == 20.0

    finalize_one = client.post(
        f"/leagues/{league['id']}/weeks/1/finalize",
        headers=auth_headers(commissioner_token),
    )
    assert finalize_one.status_code == 200
    finalize_two = client.post(
        f"/leagues/{league['id']}/weeks/1/finalize",
        headers=auth_headers(commissioner_token),
    )
    assert finalize_two.status_code == 200
    assert finalize_one.json()["standings"] == finalize_two.json()["standings"]
    assert db_session.query(FantasyPlayerScore).count() == 3
    assert db_session.query(TeamWeeklyScore).count() == 2
    assert db_session.query(Standing).count() == 2
    standing = db_session.query(Standing).filter(Standing.team_id == teams[0].id).one()
    assert standing.wins == 1
