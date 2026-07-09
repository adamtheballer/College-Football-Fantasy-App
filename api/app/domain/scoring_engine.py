from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from collegefootballfantasy_api.app.domain.scoring_rules import (
    BENCH_SLOTS,
    KICKER_POSITIONS,
    KICKER_RULES,
    NON_SCORING_SLOTS,
    OFFENSE_POSITIONS,
    OFFENSE_RULES,
    RULES_BY_PROFILE,
    SCORING_RULE_ALIASES,
    STARTING_SLOTS,
    SUPPORTED_PLAYER_POSITIONS,
    ScoringRulesValidationError,
    ValidatedScoringRules,
    default_rules_bundle,
    is_starting_slot,
    normalize_scoring_rules,
    scoring_profile_for_position,
    validate_scoring_rules,
)
from collegefootballfantasy_api.app.domain.stat_normalization import normalize_player_stats


CALCULATION_VERSION = "2026.1"
ScoreBreakdown = dict[str, dict[str, float | str] | float | list[str]]


@dataclass(frozen=True)
class ScoreResult:
    total: float
    breakdown: ScoreBreakdown
    profile: str
    warnings: list[str]
    ignored_stats: list[str]


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _round_points(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _round_category(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _validated_rules(scoring_rules: Mapping[str, Any] | ValidatedScoringRules | None) -> ValidatedScoringRules:
    if isinstance(scoring_rules, ValidatedScoringRules):
        return scoring_rules
    return validate_scoring_rules(scoring_rules)


def calculate_player_fantasy_points(
    normalized_stats: Mapping[str, Any],
    scoring_rules: Mapping[str, Any] | ValidatedScoringRules | None,
    position: str | None = None,
) -> tuple[float, ScoreBreakdown]:
    rules = _validated_rules(scoring_rules).for_position(position)
    breakdown: ScoreBreakdown = {}
    total = 0.0
    for key, multiplier in rules.items():
        stat = _number(normalized_stats.get(key))
        points = _round_category(stat * multiplier)
        breakdown[key] = {
            "stat": stat,
            "multiplier": multiplier,
            "points": points,
        }
        total += points

    rounded_total = _round_points(total)
    breakdown["total"] = rounded_total
    return rounded_total, breakdown


def calculate_score(
    stats: Mapping[str, Any] | None,
    position: str | None,
    rules: Mapping[str, Any] | ValidatedScoringRules | None = None,
) -> ScoreResult:
    profile = scoring_profile_for_position(position)
    normalized = normalize_player_stats(stats, position)
    total, breakdown = calculate_player_fantasy_points(normalized, rules or {}, position)
    return ScoreResult(
        total=total,
        breakdown=breakdown,
        profile=profile,
        warnings=[] if profile != "unsupported" else ["unsupported_position"],
        ignored_stats=[],
    )
