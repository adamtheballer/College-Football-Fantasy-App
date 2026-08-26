"""Shared, duration-aware player-value adjustments for injury availability."""
from __future__ import annotations

import re

from collegefootballfantasy_api.app.services.injury_status import normalize_injury_status


# These factors are intentionally conservative: a short-term absence changes a
# player's market value without treating a two-week injury like a season-ending
# one.  A confirmed return keeps a modest recovery discount for the current
# availability report only, and returns to 1.0 after that report clears.
SHORT_ABSENCE_VALUE_MULTIPLIER = 0.70
RETURNING_VALUE_MULTIPLIER = 0.90


def estimated_absence_weeks(return_timeline: str | None) -> int | None:
    """Extract a conservative expected absence from a reviewed timeline.

    The official feeds use short phrases (for example ``"2-4 weeks"``).  For
    ranges we use the upper bound so an uncertain return does not overvalue the
    player.  Narratives without a duration deliberately return ``None`` and
    receive the documented short-absence default below.
    """
    timeline = (return_timeline or "").casefold()
    if not timeline:
        return None
    if any(phrase in timeline for phrase in ("season ending", "out for season", "rest of season", "year ending")):
        return 12
    range_match = re.search(r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*weeks?", timeline)
    if range_match:
        return int(range_match.group(2))
    week_match = re.search(r"(\d+)\s*weeks?", timeline)
    if week_match:
        return int(week_match.group(1))
    if "week-to-week" in timeline or "week to week" in timeline:
        return 2
    return None


def injury_value_multiplier(
    status: str | None,
    *,
    return_timeline: str | None = None,
    is_returning: bool = False,
) -> float:
    """Return the shared market-value multiplier for the latest availability.

    A 2–4 week injury lands at 70% of the player's approved CFB 27 baseline;
    a player officially marked as returning is 90% for that report.  This
    function accepts raw provider labels so every caller uses the same
    normalization and does not drift from the displayed status.
    """
    normalized = normalize_injury_status(status)
    if normalized in {"FULL", "N_A"}:
        return RETURNING_VALUE_MULTIPLIER if is_returning else 1.0
    if normalized == "OUT_FOR_SEASON":
        return 0.30
    if normalized == "IR":
        weeks = estimated_absence_weeks(return_timeline)
        if weeks is not None and weeks <= 4:
            return 0.60
        return 0.45
    if normalized in {"OUT", "INACTIVE", "SUSPENDED"}:
        weeks = estimated_absence_weeks(return_timeline)
        if weeks is None:
            return SHORT_ABSENCE_VALUE_MULTIPLIER
        if weeks <= 1:
            return 0.82
        if weeks <= 4:
            return SHORT_ABSENCE_VALUE_MULTIPLIER
        if weeks <= 8:
            return 0.58
        return 0.42
    if normalized == "DOUBTFUL":
        return 0.82
    if normalized in {"QUESTIONABLE", "DAY_TO_DAY", "TBD"}:
        return 0.92
    if normalized == "PROBABLE":
        return 0.97
    return 1.0
