from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.player_trade_value import VALUE_POLICY_VERSION


def test_player_trajectory_returns_thirteen_week_league_scored_series(client, db_session):
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
            TeamSchedule(team_name="Texas", season=2026, week=1, opponent_name="Ohio State", location="home", is_bye=False),
            TeamSchedule(team_name="Texas", season=2026, week=2, location="bye", is_bye=True),
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
    assert [point["week"] for point in body["projection"]] == list(range(1, 14))
    assert [point["week"] for point in body["value"]] == list(range(1, 14))
    assert body["projection"][0] == {"week": 1, "points": 22.0, "source": "published"}
    assert body["projection"][1] == {"week": 2, "points": 0.0, "source": "bye"}
    assert body["value"][0] == {"week": 1, "value": 84.0, "source": "published"}
    assert all(0 <= point["value"] <= 100 for point in body["value"])
    assert all(point["points"] >= 0 for point in body["projection"])


def test_player_trajectory_rejects_unknown_league_context(client, db_session):
    player = Player(name="Known Player", position="WR", school="Miami", sheet_projected_season_points=200.0)
    db_session.add(player)
    db_session.commit()

    response = client.get(f"/players/{player.id}/trajectory", params={"league_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "league not found"
