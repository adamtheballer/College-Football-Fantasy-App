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

KICKER_ALIASES = {
    "fg_made_0_39": ["fg_made_0_39", "FieldGoalsMade0to39", "FieldGoalsMade0To39", "FgMade0To39"],
    "fg_made_40_49": ["fg_made_40_49", "FieldGoalsMade40to49", "FieldGoalsMade40To49", "FgMade40To49"],
    "fg_made_50_plus": ["fg_made_50_plus", "FieldGoalsMade50Plus", "FieldGoalsMade50", "FgMade50Plus"],
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
    stats = raw_stats or {}
    return {
        stat_key: _first_number(stats, aliases)
        for stat_key, aliases in aliases_for_position(position).items()
    }
