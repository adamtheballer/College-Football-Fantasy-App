from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.player_trade_value import (
    VALUE_POLICY_VERSION,
    calculate_player_trade_value,
    calculate_weekly_trade_values,
    weekly_value_weights,
)


def test_preseason_value_is_rating_only_and_post_week_one_blends_performance(db_session):
    elite = Player(name="Elite RB", position="RB", school="Texas", cfb27_overall=95, sheet_projected_season_points=260)
    mid = Player(name="Mid RB", position="RB", school="Miami", cfb27_overall=80, sheet_projected_season_points=180)
    db_session.add_all([elite, mid]); db_session.commit()
    preseason = calculate_player_trade_value(db_session, player_id=elite.id, season=2026, week=0)
    assert preseason.factor_breakdown_json["seasonPerformance"] == 0
    assert preseason.factor_breakdown_json["futureProjection"] == 0
    db_session.add_all([
        PlayerStat(player_id=elite.id, season=2026, week=1, verified=True, stats={"fantasy_points": 10}),
        PlayerStat(player_id=mid.id, season=2026, week=1, verified=True, stats={"fantasy_points": 35}),
    ]); db_session.commit()
    week_one = calculate_player_trade_value(db_session, player_id=mid.id, season=2026, week=1)
    assert week_one.factor_breakdown_json["seasonPerformance"] > 0
    assert week_one.value > 0
    assert VALUE_POLICY_VERSION == "universal_v1"


def test_value_weights_bounds_ranks_and_repeat_generation(db_session):
    first = Player(name="First WR", position="WR", school="Ohio State", cfb27_overall=99, sheet_projected_season_points=300)
    second = Player(name="Second WR", position="WR", school="Oregon", cfb27_overall=60, sheet_projected_season_points=100)
    db_session.add_all([first, second]); db_session.commit()
    assert all(abs(sum(weekly_value_weights(week)) - 1) < 0.00001 for week in range(0, 16))
    first_run = calculate_weekly_trade_values(db_session, season=2026, week=0); db_session.commit()
    second_run = calculate_weekly_trade_values(db_session, season=2026, week=0); db_session.commit()
    assert first_run["calculated"] == second_run["calculated"] == 2
    value_rows = db_session.query(__import__("collegefootballfantasy_api.app.models.player_trade_value", fromlist=["PlayerTradeValue"]).PlayerTradeValue).all()
    assert len(value_rows) == 2
    assert all(0 <= row.value <= 100 for row in value_rows)
    assert min(row.positional_value_rank for row in value_rows) == 1
