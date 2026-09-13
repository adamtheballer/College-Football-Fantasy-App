from __future__ import annotations

from typing import Any, Mapping

from collegefootballfantasy_api.app.domain.scoring_rules import scoring_profile_for_position


OFFENSE_ALIASES = {
    "pass_yards": ["pass_yards", "PassingYards", "passing_yards", "PassYards", "PassingYardage"],
    "pass_tds": ["pass_tds", "PassingTouchdowns", "PassingTD", "passing_tds", "PassTD"],
    "interceptions": ["interceptions", "passing_interceptions", "PassingInterceptions", "Interceptions"],
    "rush_yards": ["rush_yards", "RushingYards", "rushing_yards", "RushYards"],
    "rush_tds": ["rush_tds", "RushingTouchdowns", "RushingTD", "rushing_tds", "RushTD"],
    "receptions": ["receptions", "Receptions", "ReceivingReceptions", "Rec"],
    "rec_yards": ["rec_yards", "ReceivingYards", "receiving_yards", "ReceivingYardage"],
    "rec_tds": ["rec_tds", "ReceivingTouchdowns", "ReceivingTD", "receiving_tds", "RecTD"],
    "two_point_conversions": ["two_point_conversions", "TwoPointConversions", "TwoPointConversion"],
    "fumbles_lost": ["fumbles_lost", "FumblesLost", "fumblesLost"],
    "fumble_return_tds": ["fumble_return_tds", "FumbleReturnTouchdowns"],
}

# Punt returns are intentionally outside the CFFB stat and scoring contract.
# Keep this list at the normalization boundary so provider aliases, stored
# legacy JSON, and client-facing game logs cannot accidentally bring them back.
_EXCLUDED_RETURN_STAT_KEYS = frozenset({
    "puntreturns",
    "puntreturnattempts",
    "puntreturnyards",
    "puntreturntouchdowns",
    "puntreturntd",
    "puntreturntds",
    "pr",
    "pryds",
    "prtd",
})
_DERIVED_FANTASY_POINT_KEYS = frozenset({"fantasypoints", "fpts"})


def _canonical_source_key(key: object) -> str:
    return "".join(character for character in str(key).lower() if character.isalnum())


def has_excluded_return_stats(raw_stats: Mapping[str, Any] | None) -> bool:
    return any(
        _canonical_source_key(key) in _EXCLUDED_RETURN_STAT_KEYS
        for key in (raw_stats or {})
    )


def strip_unscored_return_stats(
    raw_stats: Mapping[str, Any] | None,
    *,
    remove_derived_fantasy_points: bool = False,
) -> dict[str, Any]:
    """Return public/scoring stats with punt-return and stale FPTS fields removed.

    Provider payloads may retain these raw facts for audit purposes, but the
    application must never persist or expose them as player fantasy stats.
    Derived provider FPTS is removed only when its row contains a retired
    return field, because only then can it have been calculated under the
    retired policy. Legacy FPTS-only rows have no return adjustment to make.
    """

    had_excluded_returns = has_excluded_return_stats(raw_stats)
    cleaned: dict[str, Any] = {}
    for key, value in (raw_stats or {}).items():
        canonical = _canonical_source_key(key)
        if canonical in _EXCLUDED_RETURN_STAT_KEYS:
            continue
        if (
            remove_derived_fantasy_points
            and had_excluded_returns
            and canonical in _DERIVED_FANTASY_POINT_KEYS
        ):
            continue
        cleaned[str(key)] = value
    return cleaned

KICKER_ALIASES = {
    "fg_made_0_30": ["fg_made_0_30", "FieldGoalsMade0to30", "FieldGoalsMade0To30", "FgMade0To30"],
    "fg_made_31_40": ["fg_made_31_40", "FieldGoalsMade31to40", "FieldGoalsMade31To40", "FgMade31To40"],
    "fg_made_41_50": ["fg_made_41_50", "FieldGoalsMade41to50", "FieldGoalsMade41To50", "FgMade41To50"],
    "fg_made_51_60": ["fg_made_51_60", "FieldGoalsMade51to60", "FieldGoalsMade51To60", "FgMade51To60"],
    "fg_made_61_plus": ["fg_made_61_plus", "FieldGoalsMade61Plus", "FieldGoalsMade61", "FgMade61Plus"],
    "xp_made": ["xp_made", "ExtraPointsMade", "ExtraPoints", "XpMade"],
    "fg_missed": ["fg_missed", "FieldGoalsMissed", "FgMissed"],
}

ALIASES_BY_PROFILE = {
    "offense": OFFENSE_ALIASES,
    "kicker": KICKER_ALIASES,
    "unsupported": {},
}


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _first_number(raw_stats: Mapping[str, Any], aliases: list[str]) -> float:
    for key in aliases:
        if key in raw_stats:
            return _number(raw_stats.get(key))
    lower_map = {str(key).lower(): value for key, value in raw_stats.items()}
    for key in aliases:
        value = lower_map.get(key.lower())
        if value is not None:
            return _number(value)
    return 0.0


def aliases_for_position(position: str | None) -> dict[str, list[str]]:
    if position is None:
        return {**OFFENSE_ALIASES, **KICKER_ALIASES}
    return ALIASES_BY_PROFILE[scoring_profile_for_position(position)]


def normalize_player_stats(raw_stats: Mapping[str, Any] | None, position: str | None = None) -> dict[str, Any]:
    stats = strip_unscored_return_stats(raw_stats)
    return {
        stat_key: _first_number(stats, aliases)
        for stat_key, aliases in aliases_for_position(position).items()
    }
