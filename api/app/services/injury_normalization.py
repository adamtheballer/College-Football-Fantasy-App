from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


NORMALIZED_INJURY_STATUSES = {
    "healthy",
    "questionable",
    "doubtful",
    "out",
    "season_out",
    "unknown",
}

_HEALTHY = {"", "FULL", "ACTIVE", "AVAILABLE", "HEALTHY", "PROBABLE", "CLEARED", "PLAYING"}
_QUESTIONABLE = {"QUESTIONABLE", "Q", "GAME TIME DECISION", "GTD"}
_DOUBTFUL = {"DOUBTFUL", "D"}
_OUT = {"OUT", "O", "INACTIVE", "SUSPENDED"}
_SEASON_OUT = {"SEASON OUT", "OUT FOR SEASON", "SEASON-ENDING", "IR", "INJURED RESERVE"}


def normalize_injury_status(value: str | None) -> str:
    text = (value or "").strip().upper().replace("_", " ")
    if text in _HEALTHY:
        return "healthy"
    if text in _QUESTIONABLE:
        return "questionable"
    if text in _DOUBTFUL:
        return "doubtful"
    if text in _OUT:
        return "out"
    if text in _SEASON_OUT:
        return "season_out"
    return "unknown"


def display_injury_status(value: str | None) -> str:
    normalized = normalize_injury_status(value)
    return {
        "healthy": "HEALTHY",
        "questionable": "QUESTIONABLE",
        "doubtful": "DOUBTFUL",
        "out": "OUT",
        "season_out": "SEASON_OUT",
        "unknown": "UNKNOWN",
    }[normalized]


def injury_is_active(normalized_status: str | None) -> bool:
    return (normalized_status or "unknown") not in {"healthy"}


def parse_source_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
