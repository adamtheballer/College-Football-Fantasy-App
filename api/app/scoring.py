from __future__ import annotations

import json
from typing import Any, Mapping

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.scoring_engine import (
    KICKER_RULES,
    OFFENSE_RULES,
    calculate_score,
    default_rules_bundle,
    validate_scoring_rules,
)


OFFENSIVE_SCORING_RULES = OFFENSE_RULES
KICKING_SCORING_RULES = KICKER_RULES


def get_scoring_rules() -> dict[str, Any]:
    rules = default_rules_bundle()
    if not settings.fantasy_scoring_rules_json:
        return rules

    try:
        loaded = json.loads(settings.fantasy_scoring_rules_json)
    except json.JSONDecodeError as exc:
        raise ValueError("FANTASY_SCORING_RULES_JSON must be valid JSON") from exc
    if not isinstance(loaded, dict):
        raise ValueError("FANTASY_SCORING_RULES_JSON must be a JSON object")
    return validate_scoring_rules(loaded).as_dict()


def calculate_fantasy_points(
    stats: Mapping[str, Any] | None,
    rules_bundle: Mapping[str, Any] | None = None,
    position: str | None = None,
) -> float:
    return calculate_score(stats or {}, position, rules_bundle or get_scoring_rules()).total
