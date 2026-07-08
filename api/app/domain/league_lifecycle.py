from __future__ import annotations

DRAFT_STARTED_STATUSES = {"drafting", "active", "playoffs", "completed", "archived"}
SEASON_STARTED_STATUSES = {"active", "playoffs", "completed", "archived"}
COMPLETED_GAME_STATUSES = {"final", "stat_corrected", "commissioner_adjusted"}


def normalize_league_status(status: str | None) -> str:
    if not status:
        return "created"
    if status == "pre_draft":
        return "draft_scheduled"
    return status


def has_draft_started(league_status: str | None, draft_status: str | None = None) -> bool:
    status = normalize_league_status(league_status)
    return status in DRAFT_STARTED_STATUSES or draft_status in {"live", "complete", "completed"}


def has_season_started(league_status: str | None) -> bool:
    return normalize_league_status(league_status) in SEASON_STARTED_STATUSES
