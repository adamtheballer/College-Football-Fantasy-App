from __future__ import annotations


SCHEDULED = "scheduled"
LIVE = "live"
PENDING_FINAL = "pending_final"
FINAL = "final"
STAT_CORRECTED = "stat_corrected"
COMMISSIONER_ADJUSTED = "commissioner_adjusted"

MATCHUP_STATUSES = {
    SCHEDULED,
    LIVE,
    PENDING_FINAL,
    FINAL,
    STAT_CORRECTED,
    COMMISSIONER_ADJUSTED,
}

FINAL_MATCHUP_STATUSES = {FINAL, STAT_CORRECTED, COMMISSIONER_ADJUSTED}
LIVE_REFRESH_LOCKED_STATUSES = FINAL_MATCHUP_STATUSES | {PENDING_FINAL}


def is_final_status(status: str | None) -> bool:
    return (status or "").lower() in FINAL_MATCHUP_STATUSES


def is_live_refresh_locked(status: str | None) -> bool:
    return (status or "").lower() in LIVE_REFRESH_LOCKED_STATUSES
