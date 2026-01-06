import json
from typing import Any

from collegefootballfantasy_api.app.core.config import settings


OFFENSIVE_SCORING_RULES: dict[str, float] = {
    "PassingYards": 1 / 25,
    "PassingTouchdowns": 4.0,
    "PassingInterceptions": -2.0,
    "RushingYards": 1 / 10,
    "RushingTouchdowns": 6.0,
    "Receptions": 1.0,
    "ReceivingYards": 1 / 10,
    "ReceivingTouchdowns": 6.0,
    "TwoPointConversions": 2.0,
    "FumblesLost": -2.0,
    "FumbleReturnTouchdowns": 6.0,
}

DEFENSE_SCORING_RULES: dict[str, float] = {
    "Sacks": 1.0,
    "Interceptions": 2.0,
    "FumblesRecovered": 2.0,
    "Safeties": 2.0,
    "DefensiveTouchdowns": 6.0,
    "KickReturnTouchdowns": 6.0,
    "PuntReturnTouchdowns": 6.0,
    "TwoPointConversionReturns": 2.0,
}

IDP_SCORING_RULES: dict[str, float] = {
    "SoloTackles": 1.0,
    "AssistedTackles": 0.5,
    "Sacks": 2.0,
    "SackYards": 1 / 10,
    "TacklesForLoss": 1.0,
    "QuarterbackHits": 1.0,
    "PassesDefended": 1.0,
    "Interceptions": 3.0,
    "FumblesForced": 3.0,
    "FumblesRecovered": 3.0,
    "DefensiveTouchdowns": 6.0,
    "TwoPointConversionReturns": 2.0,
}

KICKING_SCORING_RULES: dict[str, float] = {
    "ExtraPointsMade": 1.0,
    "FieldGoalsMade0To49": 3.0,
    "FieldGoalsMade50Plus": 5.0,
}

POINTS_ALLOWED_BUCKETS: list[tuple[int, int | None, float]] = [
    (0, 0, 10.0),
    (1, 6, 7.0),
    (7, 13, 4.0),
    (14, 20, 1.0),
    (21, 27, 0.0),
    (28, 34, -1.0),
    (35, None, -4.0),
]


def get_scoring_rules() -> dict[str, dict[str, float] | list[tuple[int, int | None, float]]]:
    if settings.fantasy_scoring_rules_json:
        try:
            loaded = json.loads(settings.fantasy_scoring_rules_json)
        except json.JSONDecodeError:
            return {
                "offense": OFFENSIVE_SCORING_RULES,
                "defense": DEFENSE_SCORING_RULES,
                "idp": IDP_SCORING_RULES,
                "kicker": KICKING_SCORING_RULES,
                "points_allowed": POINTS_ALLOWED_BUCKETS,
            }
        if isinstance(loaded, dict):
            rules = {
                "offense": OFFENSIVE_SCORING_RULES,
                "defense": DEFENSE_SCORING_RULES,
                "idp": IDP_SCORING_RULES,
                "kicker": KICKING_SCORING_RULES,
                "points_allowed": POINTS_ALLOWED_BUCKETS,
            }
            for key in ("offense", "defense", "idp", "kicker"):
                if isinstance(loaded.get(key), dict):
                    rules[key] = {stat: float(value) for stat, value in loaded[key].items()}
            if isinstance(loaded.get("points_allowed"), list):
                rules["points_allowed"] = loaded["points_allowed"]
            if any(k in loaded for k in ("PassingYards", "RushingYards", "ReceivingYards")):
                rules["offense"] = {stat: float(value) for stat, value in loaded.items()}
            return rules
    return {
        "offense": OFFENSIVE_SCORING_RULES,
        "defense": DEFENSE_SCORING_RULES,
        "idp": IDP_SCORING_RULES,
        "kicker": KICKING_SCORING_RULES,
        "points_allowed": POINTS_ALLOWED_BUCKETS,
    }


def _get_stat_value(stats: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        if key in stats and stats[key] is not None:
            try:
                return float(stats[key])
            except (TypeError, ValueError):
                return None
    return None


def _points_allowed_score(points_allowed: float | None, buckets: list[tuple[int, int | None, float]]) -> float:
    if points_allowed is None:
        return 0.0
    value = int(points_allowed)
    for lower, upper, points in buckets:
        if upper is None and value >= lower:
            return points
        if upper is not None and lower <= value <= upper:
            return points
    return 0.0


def _field_goal_points(stats: dict[str, Any], rules: dict[str, float]) -> float:
    made_50_plus = _get_stat_value(stats, ["FieldGoalsMade50Plus", "FieldGoalsMade50PlusYds"])
    made_total = _get_stat_value(stats, ["FieldGoalsMade", "FieldGoals"])
    made_0_49 = _get_stat_value(stats, ["FieldGoalsMade0To49", "FieldGoalsMade0to49", "FieldGoalsMade0_49"])
    if made_0_49 is None and made_total is not None and made_50_plus is not None:
        made_0_49 = max(made_total - made_50_plus, 0)
    points = 0.0
    if made_0_49 is not None:
        points += made_0_49 * rules.get("FieldGoalsMade0To49", KICKING_SCORING_RULES["FieldGoalsMade0To49"])
    if made_50_plus is not None:
        points += made_50_plus * rules.get("FieldGoalsMade50Plus", KICKING_SCORING_RULES["FieldGoalsMade50Plus"])
    return points


def _select_rule_set(position: str | None) -> str:
    if not position:
        return "offense"
    normalized = position.upper()
    if normalized in {"DST", "DEF", "D/ST"}:
        return "defense"
    if normalized in {"K", "PK"}:
        return "kicker"
    if normalized in {"DL", "DE", "DT", "LB", "ILB", "OLB", "DB", "CB", "S", "IDP"}:
        return "idp"
    return "offense"


def calculate_fantasy_points(
    stats: dict[str, Any],
    rules_bundle: dict[str, dict[str, float] | list[tuple[int, int | None, float]]] | None = None,
    position: str | None = None,
) -> float:
    if not stats:
        return 0.0
    scoring_rules = rules_bundle or get_scoring_rules()
    rule_key = _select_rule_set(position)
    rule_map = scoring_rules.get(rule_key, {})
    total = 0.0
    if isinstance(rule_map, dict):
        for stat_key, multiplier in rule_map.items():
            if rule_key == "kicker" and stat_key in {"FieldGoalsMade0To49", "FieldGoalsMade50Plus"}:
                continue
            raw_value = stats.get(stat_key)
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            total += value * float(multiplier)
    if rule_key == "kicker" and isinstance(rule_map, dict):
        total += _field_goal_points(stats, rule_map)
    if rule_key == "defense":
        points_allowed = _get_stat_value(stats, ["PointsAllowed", "DefensePointsAllowed", "PointsAllowedByDefense"])
        buckets = scoring_rules.get("points_allowed", POINTS_ALLOWED_BUCKETS)
        if isinstance(buckets, list):
            total += _points_allowed_score(points_allowed, buckets)
    return round(total, 2)
