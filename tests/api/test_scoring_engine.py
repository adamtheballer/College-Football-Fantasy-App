from collegefootballfantasy_api.app.services.scoring_service import (
    calculate_player_fantasy_points,
    is_starting_slot,
    normalize_player_stats,
)


def test_qb_scoring_works():
    stats = normalize_player_stats({"PassingYards": 275, "PassingTouchdowns": 3, "Interceptions": 1})
    points, breakdown = calculate_player_fantasy_points(stats, {})

    assert points == 21.0
    assert breakdown["pass_yards"] == {"stat": 275.0, "multiplier": 0.04, "points": 11.0}
    assert breakdown["pass_tds"]["points"] == 12.0
    assert breakdown["interceptions"]["points"] == -2.0
    assert breakdown["total"] == 21.0


def test_rb_wr_te_ppr_scoring_works():
    stats = normalize_player_stats({"Receptions": 6, "ReceivingYards": 90, "ReceivingTouchdowns": 1})
    points, _ = calculate_player_fantasy_points(stats, {"ppr": 1})

    assert points == 21.0


def test_kicker_scoring_works_if_stat_fields_exist():
    stats = normalize_player_stats({"FieldGoalsMade0to39": 1, "FieldGoalsMade40to49": 1, "FieldGoalsMade50Plus": 1, "ExtraPointsMade": 3})
    points, _ = calculate_player_fantasy_points(stats, {})

    assert points == 15.0


def test_missing_stats_score_zero():
    points, breakdown = calculate_player_fantasy_points(normalize_player_stats({}), {})

    assert points == 0.0
    assert breakdown["total"] == 0.0


def test_custom_league_scoring_changes_points():
    stats = normalize_player_stats({"PassingYards": 100, "PassingTouchdowns": 1, "Receptions": 2})
    points, _ = calculate_player_fantasy_points(stats, {"pass_yards": 0.05, "pass_td": 6, "ppr": 0.5})

    assert points == 12.0


def test_custom_interception_penalty_deducts_exactly_three_points():
    stats = normalize_player_stats({"Interceptions": 1})
    points, breakdown = calculate_player_fantasy_points(stats, {"int": -3})

    assert points == -3.0
    assert breakdown["interceptions"] == {"stat": 1.0, "multiplier": -3.0, "points": -3.0}


def test_starting_slot_detection_excludes_bench_and_ir():
    assert is_starting_slot("QB") is True
    assert is_starting_slot("FLEX") is True
    assert is_starting_slot("BENCH") is False
    assert is_starting_slot("BE") is False
    assert is_starting_slot("IR") is False
