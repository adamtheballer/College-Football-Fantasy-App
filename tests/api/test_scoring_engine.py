import json
from pathlib import Path

import pytest

from collegefootballfantasy_api.app.domain.scoring_engine import ScoringRulesValidationError, validate_scoring_rules
from collegefootballfantasy_api.app.services.scoring_service import (
    calculate_player_fantasy_points,
    is_starting_slot,
    normalize_player_stats,
)
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points


SCORING_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "scoring"


@pytest.mark.parametrize("fixture_name", ["qb_week", "rb_week", "wr_week", "te_week", "k_week"])
def test_supported_position_golden_scoring_fixtures(fixture_name):
    fixture = json.loads((SCORING_FIXTURE_DIR / f"{fixture_name}.json").read_text())
    position = fixture["position"]
    stats = normalize_player_stats(fixture["raw_stats"], position)
    points, breakdown = calculate_player_fantasy_points(stats, fixture["scoring_rules"], position)

    for key, expected in fixture["expected_normalized"].items():
        assert stats[key] == expected
    for key, expected in fixture["expected_breakdown"].items():
        assert breakdown[key] == expected
    assert points == fixture["expected_total"]


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
    assert is_starting_slot("TAXI") is False
    assert is_starting_slot("") is False


def test_unsupported_defensive_positions_do_not_score():
    assert calculate_fantasy_points({"Sacks": 4, "Interceptions": 2}, position="DST") == 0.0
    assert calculate_fantasy_points({"SoloTackles": 9, "Interceptions": 1}, position="LB") == 0.0


def test_interception_alias_is_offense_only_for_supported_positions():
    assert calculate_fantasy_points({"Interceptions": 1}, position="QB") == -2.0


@pytest.mark.parametrize(
    "rules",
    [
        {"defense": {"sacks": 1}},
        {"offense": {"unknown": 1}},
        {"pass_yards": None},
        {"pass_yards": ""},
        {"pass_yards": "not-a-number"},
        {"pass_yards": True},
        {"pass_yards": float("nan")},
        {"pass_yards": float("inf")},
        {"offense": {"pass_yards": 0.04}, "ppr": 1},
        {"PassingYards": 0.04, "pass_yards": 0.05},
    ],
)
def test_bad_scoring_config_is_rejected(rules):
    with pytest.raises(ScoringRulesValidationError):
        validate_scoring_rules(rules)
