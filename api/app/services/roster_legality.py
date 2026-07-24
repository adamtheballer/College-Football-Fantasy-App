from collections.abc import Mapping

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.roster import RosterEntry

PLAYER_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
ROSTER_SLOT_KEYS = {"QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR"}


def normalize_position(position: str | None) -> str | None:
    normalized = (position or "").strip().upper()
    return normalized if normalized in PLAYER_POSITIONS else None


def normalize_slot(slot: str | None) -> str | None:
    normalized = (slot or "").strip().upper()
    if not normalized:
        return None
    if normalized == "BE" or normalized.startswith("BENCH"):
        return "BENCH"
    if normalized.startswith("RB "):
        return "RB"
    if normalized.startswith("WR "):
        return "WR"
    return normalized if normalized in ROSTER_SLOT_KEYS else None


def normalize_roster_slot_limits(roster_slots: Mapping[str, int] | None) -> dict[str, int]:
    roster_slots = roster_slots or {}
    return {
        "QB": int(roster_slots.get("QB", 0) or 0),
        "RB": int(roster_slots.get("RB", 0) or 0),
        "WR": int(roster_slots.get("WR", 0) or 0),
        "TE": int(roster_slots.get("TE", 0) or 0),
        "FLEX": int(roster_slots.get("FLEX", 0) or 0),
        "SUPERFLEX": int(roster_slots.get("SUPERFLEX", 0) or 0),
        "K": int(roster_slots.get("K", 0) or 0),
        "BENCH": int(roster_slots.get("BENCH", roster_slots.get("BE", 0)) or 0),
        "IR": int(roster_slots.get("IR", 0) or 0),
    }


def eligible_slots_for_position(position: str, superflex_enabled: bool = False) -> list[str]:
    normalized = normalize_position(position)
    if normalized == "QB":
        return ["QB", "SUPERFLEX", "BENCH"] if superflex_enabled else ["QB", "BENCH"]
    if normalized in {"RB", "WR", "TE"}:
        return [normalized, "FLEX", "BENCH"]
    if normalized == "K":
        return ["K", "BENCH"]
    return []


def superflex_is_enabled(
    roster_slots: Mapping[str, int] | None,
    *,
    configured: bool = False,
) -> bool:
    """A configured SUPERFLEX slot is authoritative for legacy settings rows."""
    return configured or normalize_roster_slot_limits(roster_slots).get("SUPERFLEX", 0) > 0


def count_roster_slots(entries: list[RosterEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        slot = normalize_slot(entry.slot)
        if not slot:
            continue
        counts[slot] = counts.get(slot, 0) + 1
    return counts


def assign_best_roster_slot_for_position(
    player_position: str,
    roster_entries: list[RosterEntry],
    roster_slots: Mapping[str, int] | None,
    *,
    superflex_enabled: bool = False,
) -> str | None:
    normalized_position = normalize_position(player_position)
    if not normalized_position:
        return None

    slot_limits = normalize_roster_slot_limits(roster_slots)
    counts = count_roster_slots(roster_entries)
    for slot in eligible_slots_for_position(
        normalized_position,
        superflex_is_enabled(slot_limits, configured=superflex_enabled),
    ):
        if slot_limits.get(slot, 0) > counts.get(slot, 0):
            return slot
    return None


def assign_best_roster_slot_for_team(
    db: Session,
    team_id: int,
    player_position: str,
    roster_slots: Mapping[str, int] | None,
    *,
    superflex_enabled: bool = False,
) -> str | None:
    roster_entries = db.query(RosterEntry).filter(RosterEntry.team_id == team_id).all()
    return assign_best_roster_slot_for_position(
        player_position,
        roster_entries,
        roster_slots,
        superflex_enabled=superflex_enabled,
    )
