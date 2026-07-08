from datetime import datetime, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.watchlist import Watchlist, WatchlistPlayer
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user(client, suffix: str) -> dict:
    response = client.post(
        "/auth/signup",
        json={"first_name": f"Pool{suffix}", "email": f"pool-{suffix}@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 201
    payload = response.json()
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == f"pool-{suffix}@example.com").one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return {"user": payload["user"], "access_token": payload["access_token"]}


def create_league(client, token: str, name: str = "Player Pool League") -> dict:
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
                "scoring_json": {"ppr": 1, "pass_tds": 6},
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


def seed_player_pool(db_session, league_id: int, user_id: int):
    team = db_session.query(Team).filter(Team.league_id == league_id).order_by(Team.id.asc()).first()
    owned = Player(name="Alpha Owned RB", position="RB", school="Texas", player_class="JR")
    free = Player(name="Beta Free WR", position="WR", school="Oregon", player_class="SO")
    injured = Player(name="Gamma Injured QB", position="QB", school="Michigan", player_class="SR")
    db_session.add_all([owned, free, injured])
    db_session.flush()
    db_session.add(RosterEntry(league_id=league_id, team_id=team.id, player_id=owned.id, slot="RB", status="active"))
    db_session.add_all(
        [
            WeeklyProjection(player_id=owned.id, season=2026, week=1, rush_yards=80, rush_tds=1, fantasy_points=14),
            WeeklyProjection(player_id=free.id, season=2026, week=1, receptions=5, rec_yards=70, rec_tds=1, fantasy_points=13),
            WeeklyProjection(player_id=injured.id, season=2026, week=1, pass_yards=250, pass_tds=2, fantasy_points=18),
            Injury(player_id=injured.id, season=2026, week=1, status="QUESTIONABLE", injury="Ankle", notes="Limited practice"),
            PlayerStat(player_id=free.id, season=2025, week=0, source="fixture", stats={"receptions": 40, "rec_yards": 650}),
            PlayerWeekScore(league_id=league_id, player_id=free.id, season=2026, week=1, fantasy_points=19.5, breakdown_json={}),
            Game(season=2026, week=1, home_team="Oregon", away_team="Texas", start_date=datetime(2026, 9, 5, 20, 0, tzinfo=timezone.utc)),
        ]
    )
    watchlist = Watchlist(user_id=user_id, league_id=league_id, name="Targets")
    db_session.add(watchlist)
    db_session.flush()
    db_session.add(WatchlistPlayer(watchlist_id=watchlist.id, player_id=free.id))
    db_session.commit()
    return owned, free, injured


def test_player_pool_is_league_aware_and_backend_filtered(client, db_session):
    identity = create_user(client, "league")
    league = create_league(client, identity["access_token"])
    owned, free, injured = seed_player_pool(db_session, league["id"], identity["user"]["id"])

    response = client.get(
        "/players/pool",
        params={"league_id": league["id"], "season": 2026, "week": 1, "availability": "free_agent", "sort": "projection"},
        headers=auth_headers(identity["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    player_ids = [row["player"]["id"] for row in body["data"]]
    assert free.id in player_ids
    assert owned.id not in player_ids
    free_row = next(row for row in body["data"] if row["player"]["id"] == free.id)
    assert free_row["availability"]["status"] == "free_agent"
    assert free_row["watchlisted"] is True
    assert free_row["projection"]["scoring_context"] == "league"
    assert free_row["recent_trend"]["latest_points"] == 19.5

    injury_response = client.get(
        "/players/pool",
        params={"league_id": league["id"], "season": 2026, "week": 1, "injury_status": "QUESTIONABLE"},
        headers=auth_headers(identity["access_token"]),
    )
    assert injury_response.status_code == 200
    assert [row["player"]["id"] for row in injury_response.json()["data"]] == [injured.id]


def test_player_pool_requires_membership_for_league_context(client, db_session):
    owner = create_user(client, "owner")
    outsider = create_user(client, "outsider")
    league = create_league(client, owner["access_token"], "Protected Player Pool")
    seed_player_pool(db_session, league["id"], owner["user"]["id"])

    no_auth = client.get("/players/pool", params={"league_id": league["id"]})
    assert no_auth.status_code == 401

    forbidden = client.get(
        "/players/pool",
        params={"league_id": league["id"]},
        headers=auth_headers(outsider["access_token"]),
    )
    assert forbidden.status_code == 403


def test_player_profile_aggregates_decision_context(client, db_session):
    identity = create_user(client, "profile")
    league = create_league(client, identity["access_token"], "Profile League")
    owned, free, injured = seed_player_pool(db_session, league["id"], identity["user"]["id"])

    response = client.get(
        f"/players/{free.id}/profile",
        params={"league_id": league["id"], "season": 2026, "week": 1},
        headers=auth_headers(identity["access_token"]),
    )
    assert response.status_code == 200
    profile = response.json()
    assert profile["player"]["id"] == free.id
    assert profile["availability"]["status"] == "free_agent"
    assert profile["watchlisted"] is True
    assert profile["projection"]["scoring_context"] == "league"
    assert profile["stats"][0]["season"] == 2025
    assert profile["schedule"][0]["opponent"] == "Texas"
    assert profile["recent_trend"]["average_points"] == 19.5

    injured_response = client.get(
        f"/players/{injured.id}/profile",
        params={"league_id": league["id"], "season": 2026, "week": 1},
        headers=auth_headers(identity["access_token"]),
    )
    assert injured_response.status_code == 200
    assert injured_response.json()["injury"]["status"] == "QUESTIONABLE"
    assert injured_response.json()["news"][0]["type"] == "injury"
