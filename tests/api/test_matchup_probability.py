import math

import pytest

from collegefootballfantasy_api.app.services.matchup_probability import (
    calculate_matchup_win_probability,
)


@pytest.mark.parametrize(
    ("team_a", "team_b", "expected"),
    [
        (100.0, 100.0, (50.0, 50.0)),
        (100.0, 102.0, (49.0, 51.0)),
        (133.1, 137.1, (48.0, 52.0)),
        (133.1, 137.0, (48.05, 51.95)),
        (100.0, 110.0, (45.0, 55.0)),
        (100.0, 115.0, (38.75, 61.25)),
        (100.0, 120.0, (30.0, 70.0)),
        (0.0, 200.0, (5.0, 95.0)),
    ],
)
def test_projected_win_probability_uses_the_approved_piecewise_curve(team_a, team_b, expected):
    assert calculate_matchup_win_probability(team_a, team_b) == expected


def test_projected_win_probability_is_symmetric_and_monotonic():
    for margin in range(0, 101):
        forward = calculate_matchup_win_probability(100.0, 100.0 + margin)
        reverse = calculate_matchup_win_probability(100.0 + margin, 100.0)
        assert forward is not None
        assert reverse is not None
        assert forward == (reverse[1], reverse[0])
        if margin:
            prior = calculate_matchup_win_probability(100.0, 99.0 + margin)
            assert prior is not None
            assert reverse[0] >= prior[0]


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -0.1])
def test_projected_win_probability_is_unavailable_for_invalid_or_missing_totals(value):
    assert calculate_matchup_win_probability(value, 100.0) is None


def test_projected_win_probability_accepts_a_legitimate_zero_total():
    assert calculate_matchup_win_probability(0.0, 0.0) == (50.0, 50.0)
    assert math.isclose(calculate_matchup_win_probability(0.0, 1.0)[0], 49.5)
