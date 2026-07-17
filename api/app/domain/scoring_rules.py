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
}

KICKER_RULES: dict[str, float] = {
    "fg_made_0_39": 3,
    "fg_made_40_49": 4,
    "fg_made_50_plus": 5,
    "xp_made": 1,
    "fg_missed": -1,
}

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
    "fg": "fg_made_0_39",
    "xp": "xp_made",
    "FieldGoalsMade0To49": "fg_made_0_39",
    "FieldGoalsMade0to49": "fg_made_0_39",
    "FieldGoalsMade0To39": "fg_made_0_39",
    "FieldGoalsMade0to39": "fg_made_0_39",
    "FieldGoalsMade40To49": "fg_made_40_49",
    "FieldGoalsMade40to49": "fg_made_40_49",
    "FieldGoalsMade50Plus": "fg_made_50_plus",
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
