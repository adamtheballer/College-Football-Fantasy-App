import json
from pathlib import Path

import pytest

from collegefootballfantasy_api.app.services.scoring_service import (
    calculate_player_fantasy_points,
    normalize_player_stats,
)


SCORING_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "scoring"
SUPPORTED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


@pytest.mark.parametrize("fixture_path", sorted(SCORING_FIXTURE_DIR.glob("*_week.json")), ids=lambda path: path.stem)
def test_golden_provider_scoring_fixture_matches_expected_breakdown(fixture_path: Path):
    fixture = json.loads(fixture_path.read_text())
    position = fixture["position"]

    assert position in SUPPORTED_POSITIONS

    normalized_stats = normalize_player_stats(fixture["raw_stats"], position)
    fantasy_points, breakdown = calculate_player_fantasy_points(
        normalized_stats,
        fixture["scoring_rules"],
        position,
    )

    assert normalized_stats == {**normalized_stats, **fixture["expected_normalized"]}
    for key, expected in fixture["expected_breakdown"].items():
        assert breakdown[key] == expected
    assert fantasy_points == fixture["expected_total"]


def test_golden_fixture_suite_is_limited_to_supported_skill_positions():
    fixture_positions = {
        json.loads(fixture_path.read_text())["position"]
        for fixture_path in SCORING_FIXTURE_DIR.glob("*_week.json")
    }

    assert fixture_positions == SUPPORTED_POSITIONS
