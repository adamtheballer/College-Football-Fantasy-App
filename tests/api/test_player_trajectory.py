from datetime import date, datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.player_trade_value import VALUE_POLICY_VERSION


def test_player_trajectory_returns_only_the_preseason_snapshot_before_week_one(client, db_session):
    player = Player(
        name="Trajectory Runner",
        position="RB",
        school="Texas",
        cfb27_overall=92,
        sheet_projected_season_points=260.0,
    )
    db_session.add(player)
    db_session.flush()
    league = League(name="Trajectory League", season_year=2026)
    db_session.add(league)
    db_session.flush()
    db_session.add_all(
        [
            LeagueSettings(league_id=league.id, scoring_json={"rush_yards": 0.2, "rush_tds": 6}),
            TeamSchedule(team_name="Texas", season=2026, week=1, opponent_name="Ohio State", location="home", is_bye=False, game_date=date.today() + timedelta(days=30)),
            TeamSchedule(team_name="Texas", season=2026, week=2, location="bye", is_bye=True, game_date=date.today() + timedelta(days=37)),
            WeeklyProjection(
                player_id=player.id,
                season=2026,
                week=1,
                is_published=True,
                rush_yards=80.0,
                rush_tds=1.0,
                fantasy_points=14.0,
            ),
            PlayerTradeValue(
                player_id=player.id,
                season=2026,
                week=1,
                value=84.0,
                tier="ELITE",
                confidence=0.9,
                policy_version=VALUE_POLICY_VERSION,
                calculated_at=datetime.now(timezone.utc),
                input_version="test",
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/trajectory", params={"season": 2026, "league_id": league.id})

    assert response.status_code == 200
    body = response.json()
    assert [point["week"] for point in body["projection"]] == [0]
    assert [point["week"] for point in body["value"]] == [0]
    assert body["projection"][0]["source"] == "preseason"
    assert body["value"][0]["source"] == "preseason"
    assert all(0 <= point["value"] <= 100 for point in body["value"])
    assert all(point["points"] >= 0 for point in body["projection"])


def test_player_trajectory_adds_weekly_snapshots_only_after_the_week_starts(client, db_session):
    player = Player(name="Started Week Runner", position="RB", school="Texas", cfb27_overall=92, sheet_projected_season_points=260.0)
    db_session.add(player)
    db_session.flush()
    db_session.add_all(
        [
            TeamSchedule(team_name="Texas", season=2026, week=1, opponent_name="Ohio State", location="home", is_bye=False, game_date=date.today() - timedelta(days=1)),
            WeeklyProjection(player_id=player.id, season=2026, week=1, is_published=True, rush_yards=80.0, rush_tds=1.0, fantasy_points=14.0),
            PlayerTradeValue(player_id=player.id, season=2026, week=1, value=84.0, tier="ELITE", confidence=0.9, policy_version=VALUE_POLICY_VERSION, calculated_at=datetime.now(timezone.utc), input_version="test"),
        ]
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/trajectory", params={"season": 2026})

    assert response.status_code == 200
    body = response.json()
    assert [point["week"] for point in body["projection"]] == [0, 1]
    assert body["projection"][1] == {"week": 1, "points": 14.0, "source": "published"}
    assert [point["week"] for point in body["value"]] == [0, 1]
    assert body["value"][1] == {"week": 1, "value": 84.0, "source": "published"}


def test_player_trajectory_rejects_unknown_league_context(client, db_session):
    player = Player(name="Known Player", position="WR", school="Miami", sheet_projected_season_points=200.0)
    db_session.add(player)
    db_session.commit()

    response = client.get(f"/players/{player.id}/trajectory", params={"league_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "league not found"
