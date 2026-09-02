"""A single, explainable outcome range for weekly fantasy projections.

The median projection is the model's expected fantasy score.  ``floor`` and
``ceiling`` are not arbitrary display values: they are lower- and upper-tail
outcomes from the same weighted normal distribution.  ``bust_prob`` is the
probability of finishing at or below the displayed floor and ``boom_prob`` is
the probability of finishing at or above the displayed ceiling.

Keeping those four values coupled prevents a player card from showing a
ceiling that does not match its boom percentage (or a floor that does not
match its bust percentage).
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt


_POSITION_VOLATILITY = {
    "QB": 0.28,
    "RB": 0.32,
    "WR": 0.36,
    "TE": 0.38,
    "K": 0.30,
    "PK": 0.30,
}
_POSITION_MIN_SD = {
    "QB": 2.5,
    "RB": 2.0,
    "WR": 2.0,
    "TE": 1.8,
    "K": 1.5,
    "PK": 1.5,
}
_POSITION_EXPECTED_OPPORTUNITIES = {
    "QB": 34.0,
    "RB": 18.0,
    "WR": 9.0,
    "TE": 6.0,
    "K": 4.0,
    "PK": 4.0,
}


@dataclass(frozen=True)
class ProjectionOutcomeRange:
    floor: float
    ceiling: float
    boom_prob: float
    bust_prob: float


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _normal_cdf(value: float, mean: float, standard_deviation: float) -> float:
    if standard_deviation <= 0:
        return 0.0
    z_score = (value - mean) / (standard_deviation * sqrt(2))
    return 0.5 * (1 + erf(z_score))


def weighted_projection_outcomes(
    fantasy_points: float | None,
    *,
    position: str | None,
    expected_opportunities: float | None = None,
    availability_multiplier: float | None = None,
) -> ProjectionOutcomeRange:
    """Calculate coupled fantasy outcome range and tail probabilities.

    The distribution's spread is weighted by position, projected opportunity,
    and availability uncertainty.  High-volume, fully available players have
    tighter ranges; volatile positions, low-volume roles, and uncertain
    availability have wider ranges.  The tail cutoffs use that same spread,
    making the displayed boom/bust percentages the actual probabilities of
    reaching the displayed ceiling/floor.
    """

    median = max(0.0, float(fantasy_points or 0.0))
    if median <= 0:
        return ProjectionOutcomeRange(floor=0.0, ceiling=0.0, boom_prob=0.0, bust_prob=0.0)

    normalized_position = (position or "").upper()
    base_volatility = _POSITION_VOLATILITY.get(normalized_position, 0.34)
    minimum_sd = _POSITION_MIN_SD.get(normalized_position, 2.0)
    expected_volume = _POSITION_EXPECTED_OPPORTUNITIES.get(normalized_position, 10.0)
    opportunities = max(0.0, float(expected_opportunities or 0.0))
    # Missing opportunity data should use the position baseline, rather than
    # making an imported preseason projection look artificially certain.
    volume_ratio = opportunities / expected_volume if opportunities > 0 else 1.0
    volume_weight = _clamp(1.18 - (0.24 * min(volume_ratio, 1.5)), 0.84, 1.18)
    availability = _clamp(float(availability_multiplier if availability_multiplier is not None else 1.0), 0.0, 1.0)
    availability_weight = 1.0 + ((1.0 - availability) * 0.35)
    risk_weight = volume_weight * availability_weight
    standard_deviation = max(minimum_sd, median * base_volatility * risk_weight)

    # Tail weights express how far from the median the labelled outcome sits.
    # A volatile role already carries a wider standard deviation, so it gets a
    # slightly *closer* tail cutoff. That makes the manager-facing labels do
    # what they say: volatile, low-volume players have both a wider range and
    # higher boom/bust probabilities than dependable high-volume players.
    boom_weight = 1.40 - (0.25 * risk_weight)
    bust_weight = 1.30 - (0.25 * risk_weight)
    floor = max(0.0, median - (bust_weight * standard_deviation))
    ceiling = median + (boom_weight * standard_deviation)
    # Persist/display the range to one decimal and evaluate the tail at those
    # same displayed values.  This keeps the percentage mathematically tied to
    # the number a manager can actually see.
    floor = round(floor, 1)
    ceiling = round(ceiling, 1)
    boom_probability = 1.0 - _normal_cdf(ceiling, median, standard_deviation)
    bust_probability = _normal_cdf(floor, median, standard_deviation)

    return ProjectionOutcomeRange(
        floor=floor,
        ceiling=ceiling,
        boom_prob=round(_clamp(boom_probability, 0.01, 0.49), 4),
        bust_prob=round(_clamp(bust_probability, 0.01, 0.49), 4),
    )
