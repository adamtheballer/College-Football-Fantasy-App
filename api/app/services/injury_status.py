from __future__ import annotations


def normalize_injury_status(raw_status: str | None) -> str:
    """Return the canonical reviewed-injury designation used by all API readers."""
    status = " ".join((raw_status or "FULL").strip().upper().replace("_", " ").replace("-", " ").split())

    if status in {"", "FULL", "HEALTHY", "ACTIVE", "AVAILABLE"}:
        return "FULL"
    if status in {"N/A", "NA", "NOT APPLICABLE"}:
        return "N_A"
    if status in {"TBD", "TO BE DETERMINED"}:
        return "TBD"
    if any(token in status for token in ("OUT FOR SEASON", "SEASON ENDING", "SEASON END", "LOST FOR THE SEASON")):
        return "OUT_FOR_SEASON"
    if "DAY TO DAY" in status:
        return "DAY_TO_DAY"
    if "SUSPEND" in status:
        return "SUSPENDED"
    if "INACTIVE" in status:
        return "INACTIVE"
    if status == "IR" or "INJURED RESERVE" in status:
        return "IR"
    if "OUT" in status:
        return "OUT"
    if "DOUBTFUL" in status:
        return "DOUBTFUL"
    if "QUESTION" in status or "GTD" in status or "GAME TIME" in status:
        return "QUESTIONABLE"
    if "PROBABLE" in status:
        return "PROBABLE"
    return "FULL"


def is_current_injury_designation(status: str | None) -> bool:
    """Whether a normalized status is an active, informational injury designation."""
    return normalize_injury_status(status) not in {"FULL", "N_A"}
