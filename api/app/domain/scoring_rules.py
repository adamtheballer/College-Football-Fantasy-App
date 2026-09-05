from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


OFFENSE_POSITIONS = {"QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX"}
KICKER_POSITIONS = {"K", "PK"}
SUPPORTED_PLAYER_POSITIONS = OFFENSE_POSITIONS | KICKER_POSITIONS
STARTING_SLOTS = OFFENSE_POSITIONS | KICKER_POSITIONS | {"DST", "DEF"}
BENCH_SLOTS = {"BE", "BENCH"}
NON_SCORING_SLOTS = {"IR", "INJURED_RESERVE", "TAXI", "RESERVE", "OUT", "NA"}
SUPPORTED_SCORING_PROFILES = {"offense", "kicker"}

OFFENSE_RULES: dict[str, float] = {
    "pass_yards": 0.04,
    "pass_tds": 4,
    "interceptions": -2,
    "rush_yards": 0.1,
    "rush_tds": 6,
    "receptions": 1,
    "rec_yards": 0.1,
    "rec_tds": 6,
    "two_point_conversions": 2,
    "fumbles_lost": -2,
    "fumble_return_tds": 6,
    # Special-teams returns are not receptions or rushing attempts. Keep
    # their independent provider fields so a punt-return touchdown earns the
    # same six points as another offensive touchdown without PPR leakage.
    "punt_return_yards": 0.1,
    "punt_return_tds": 6,
}

KICKER_RULES: dict[str, float] = {
    "fg_made_0_30": 3,
    "fg_made_31_40": 3,
    "fg_made_41_50": 4,
    "fg_made_51_60": 5,
    "fg_made_61_plus": 5,
    "xp_made": 1,
    "fg_missed": 0,
}

# Kept solely to identify and audit the former beta default.  It must never be
# used for new league creation or present-day scoring.
LEGACY_BETA_KICKER_RULES: dict[str, float] = {
    "fg_made_0_30": 3,
    "fg_made_31_40": 3,
    "fg_made_41_50": 3,
    "fg_made_51_60": 3,
    "fg_made_61_plus": 3,
    "xp_made": 1,
}

# Kept solely to target the pre-Week-1 3/5/7/9/11 policy for the versioned
# correction.  Do not derive this from KICKER_RULES: production migrations must
# retain the exact historic policy they are allowed to alter.
PREVIOUS_KICKER_RULES: dict[str, float] = {
    "fg_made_0_30": 3,
    "fg_made_31_40": 5,
    "fg_made_41_50": 7,
    "fg_made_51_60": 9,
    "fg_made_61_plus": 11,
    "xp_made": 1,
    "fg_missed": -1,
}

# Public beta league creation uses the same canonical rule set as the scoring
# engine, including an explicit zero for missed field goals.
BETA_KICKER_RULES: dict[str, float] = KICKER_RULES.copy()

RULES_BY_PROFILE = {
    "offense": OFFENSE_RULES,
    "kicker": KICKER_RULES,
    "unsupported": {},
}

SCORING_RULE_ALIASES = {
    "ppr": "receptions",
    "PassingYards": "pass_yards",
    "PassingTouchdowns": "pass_tds",
    "PassingInterceptions": "interceptions",
    "RushingYards": "rush_yards",
    "RushingTouchdowns": "rush_tds",
    "ReceivingYards": "rec_yards",
    "ReceivingTouchdowns": "rec_tds",
    "Receptions": "receptions",
    "TwoPointConversions": "two_point_conversions",
    "FumblesLost": "fumbles_lost",
    "FumbleReturnTouchdowns": "fumble_return_tds",
    "PuntReturnYards": "punt_return_yards",
    "PuntReturnTouchdowns": "punt_return_tds",
    "PuntReturnTD": "punt_return_tds",
    "PuntReturnTDs": "punt_return_tds",
    "pass_td": "pass_tds",
    "passing_td": "pass_tds",
    "passing_tds": "pass_tds",
    "pass_int": "interceptions",
    "passing_interceptions": "interceptions",
    "interception": "interceptions",
    "interceptions": "interceptions",
    "int": "interceptions",
    "rush_td": "rush_tds",
    "rushing_td": "rush_tds",
    "rushing_tds": "rush_tds",
    "rec_td": "rec_tds",
    "receiving_td": "rec_tds",
    "receiving_tds": "rec_tds",
    "pass_yd": "pass_yards",
    "passing_yards": "pass_yards",
    "rush_yd": "rush_yards",
    "rushing_yards": "rush_yards",
    "receiving_yards": "rec_yards",
    "fumble_lost": "fumbles_lost",
    "xp": "xp_made",
    "FieldGoalsMade0To30": "fg_made_0_30",
    "FieldGoalsMade0to30": "fg_made_0_30",
    "FieldGoalsMade31To40": "fg_made_31_40",
    "FieldGoalsMade31to40": "fg_made_31_40",
    "FieldGoalsMade41To50": "fg_made_41_50",
    "FieldGoalsMade41to50": "fg_made_41_50",
    "FieldGoalsMade51To60": "fg_made_51_60",
    "FieldGoalsMade51to60": "fg_made_51_60",
    "FieldGoalsMade61Plus": "fg_made_61_plus",
    # The old three-bucket names remain accepted for stored legacy settings.
    "fg_made_0_39": "fg_made_0_30",
    "fg_made_40_49": "fg_made_31_40",
    "fg_made_50_plus": "fg_made_41_50",
    "ExtraPointsMade": "xp_made",
    "FieldGoalsMissed": "fg_missed",
}

YARDS_PER_POINT_ALIASES = {
    "pass_yds_per_pt": "pass_yards",
    "rush_yds_per_pt": "rush_yards",
    "rec_yds_per_pt": "rec_yards",
}


@dataclass(frozen=True)
class ValidatedScoringRules:
    offense: dict[str, float]
    kicker: dict[str, float]

    def for_position(self, position: str | None = None) -> dict[str, float]:
        if position is None:
            return {**self.offense, **self.kicker}
        profile = scoring_profile_for_position(position)
        if profile == "kicker":
            return self.kicker.copy()
        if profile == "unsupported":
            return {}
        return self.offense.copy()

    def as_dict(self) -> dict[str, dict[str, float]]:
        return {"offense": self.offense.copy(), "kicker": self.kicker.copy()}


class ScoringRulesValidationError(ValueError):
    pass


def scoring_profile_for_position(position: str | None) -> str:
    if position is None:
        return "offense"
    normalized = position.upper()
    if normalized in KICKER_POSITIONS:
        return "kicker"
    if normalized in OFFENSE_POSITIONS:
        return "offense"
    return "unsupported"


def is_starting_slot(slot: str) -> bool:
    normalized = (slot or "").upper()
    if normalized in BENCH_SLOTS or normalized in NON_SCORING_SLOTS:
        return False
    return normalized in STARTING_SLOTS


def _coerce_rule_value(key: str, value: Any) -> float:
    if value is None or value == "":
        raise ScoringRulesValidationError(f"scoring rule {key!r} must be a finite number")
    if isinstance(value, bool):
        raise ScoringRulesValidationError(f"scoring rule {key!r} must be numeric, not boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ScoringRulesValidationError(f"scoring rule {key!r} must be a finite number") from exc
    if not math.isfinite(number):
        raise ScoringRulesValidationError(f"scoring rule {key!r} must be finite")
    return number


def field_goal_tier_rules(base_points: Any) -> dict[str, float]:
    """Build the 0-40/base, 41-50/+1, and 51+/+2 field-goal schedule."""
    base = _coerce_rule_value("fg", base_points)
    return {
        "fg_made_0_30": base,
        "fg_made_31_40": base,
        "fg_made_41_50": base + 1,
        "fg_made_51_60": base + 2,
        "fg_made_61_plus": base + 2,
        "fg_missed": 0,
    }


def apply_beta_kicker_scoring(scoring_rules: Mapping[str, Any]) -> dict[str, Any]:
    """Force the public-beta kicker policy after request normalization."""

    return {**scoring_rules, **BETA_KICKER_RULES}


def _canonical_rule_key(raw_key: str, allowed: set[str]) -> str:
    canonical = SCORING_RULE_ALIASES.get(raw_key, raw_key)
    if canonical not in allowed:
        raise ScoringRulesValidationError(f"unknown scoring rule {raw_key!r}")
    return canonical


def _normalize_profile_rules(profile: str, raw_rules: Mapping[str, Any]) -> dict[str, float]:
    defaults = RULES_BY_PROFILE[profile].copy()
    seen_aliases: dict[str, str] = {}
    for raw_key, raw_value in raw_rules.items():
        key = str(raw_key)
        canonical = _canonical_rule_key(key, set(defaults))
        previous = seen_aliases.get(canonical)
        if previous is not None and previous != key:
            raise ScoringRulesValidationError(
                f"ambiguous scoring aliases {previous!r} and {key!r} both map to {canonical!r}"
            )
        seen_aliases[canonical] = key
        defaults[canonical] = _coerce_rule_value(key, raw_value)
    return defaults


def _partition_flat_rules(raw_rules: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    offense_raw: dict[str, Any] = {}
    kicker_raw: dict[str, Any] = {}
    for raw_key, raw_value in raw_rules.items():
        key = str(raw_key)
        if key == "fg":
            if kicker_raw:
                raise ScoringRulesValidationError("field-goal base cannot be mixed with individual field-goal tiers")
            kicker_raw.update(field_goal_tier_rules(raw_value))
            continue
        yards_target = YARDS_PER_POINT_ALIASES.get(key)
        if yards_target is not None:
            if yards_target in offense_raw:
                raise ScoringRulesValidationError(
                    f"ambiguous scoring aliases for {yards_target!r}"
                )
            yards_per_point = _coerce_rule_value(key, raw_value)
            if yards_per_point <= 0:
                raise ScoringRulesValidationError(f"scoring rule {key!r} must be greater than zero")
            offense_raw[yards_target] = 1 / yards_per_point
            continue
        canonical = SCORING_RULE_ALIASES.get(key, key)
        in_offense = canonical in OFFENSE_RULES
        in_kicker = canonical in KICKER_RULES
        if in_offense and in_kicker:
            raise ScoringRulesValidationError(f"ambiguous scoring rule {key!r}")
        if in_offense:
            offense_raw[key] = raw_value
            continue
        if in_kicker:
            kicker_raw[key] = raw_value
            continue
        raise ScoringRulesValidationError(f"unknown scoring rule {key!r}")
    return offense_raw, kicker_raw


def validate_scoring_rules(raw_rules: Mapping[str, Any] | None) -> ValidatedScoringRules:
    if raw_rules is None:
        return ValidatedScoringRules(offense=OFFENSE_RULES.copy(), kicker=KICKER_RULES.copy())
    if not isinstance(raw_rules, Mapping):
        raise ScoringRulesValidationError("scoring rules must be a JSON object")

    nested_profiles = {
        str(key)
        for key, value in raw_rules.items()
        if isinstance(value, Mapping)
    }
    unknown_profiles = nested_profiles - SUPPORTED_SCORING_PROFILES
    if unknown_profiles:
        raise ScoringRulesValidationError(f"unknown scoring profile {sorted(unknown_profiles)[0]!r}")

    offense_raw = raw_rules.get("offense") if isinstance(raw_rules.get("offense"), Mapping) else {}
    kicker_raw = raw_rules.get("kicker") if isinstance(raw_rules.get("kicker"), Mapping) else {}
    flat_raw = {
        str(key): value
        for key, value in raw_rules.items()
        if not isinstance(value, Mapping)
    }

    if nested_profiles and flat_raw:
        raise ScoringRulesValidationError("scoring rules cannot mix nested profiles and flat keys")

    if not nested_profiles:
        offense_flat, kicker_flat = _partition_flat_rules(flat_raw)
        offense = _normalize_profile_rules("offense", offense_flat)
        kicker = _normalize_profile_rules("kicker", kicker_flat)
    else:
        offense = _normalize_profile_rules("offense", offense_raw)  # type: ignore[arg-type]
        kicker = _normalize_profile_rules("kicker", kicker_raw)  # type: ignore[arg-type]

    return ValidatedScoringRules(offense=offense, kicker=kicker)


def normalize_scoring_rules(raw_rules: Mapping[str, Any] | None) -> ValidatedScoringRules:
    return validate_scoring_rules(raw_rules)


def default_rules_bundle() -> dict[str, dict[str, float]]:
    return validate_scoring_rules({}).as_dict()
