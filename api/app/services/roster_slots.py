"""Canonical roster-slot construction shared by roster and matchup surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.services.roster_legality import (
    eligible_slots_for_position,
    normalize_roster_slot_limits,
    normalize_slot,
    superflex_is_enabled,
)


ROSTER_SLOT_ORDER = ("QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR")


class RosterSlotIntegrityError(ValueError):
    """Raised when an occupied assignment cannot be overlaid on the configured roster."""


@dataclass(slots=True)
class CanonicalRosterSlot:
    slot_id: str
    slot_type: str
    slot_index: int
    display_label: str
    is_starter: bool
    is_ir: bool
    entry: RosterEntry | None = None


def roster_slot_key(team_id: int, slot_type: str, slot_index: int) -> str:
    return f"team-{team_id}-{slot_type}-{slot_index}"


def slot_display_label(slot_type: str, slot_index: int, slot_count: int) -> str:
    if slot_type == "BENCH":
        return f"Bench {slot_index}"
    if slot_type == "IR" and slot_count > 1:
        return f"IR {slot_index}"
    return slot_type


def build_team_roster_slots(
    team_id: int,
    roster_slots: Mapping[str, int] | None,
    roster_entries: list[RosterEntry],
) -> list[CanonicalRosterSlot]:
    """Build every logical roster slot then overlay occupied assignments.

    Slot identity is derived exclusively from the team's configured roster shape, never
    from a player or a ``RosterEntry`` primary key. This preserves a vacated QB/RB/etc.
    after an assignment row is deleted.
    """
    limits = normalize_roster_slot_limits(roster_slots)
    slots: list[CanonicalRosterSlot] = []
    by_assignment_key: dict[tuple[str, int], CanonicalRosterSlot] = {}
    for slot_type in ROSTER_SLOT_ORDER:
        slot_count = max(0, int(limits.get(slot_type, 0)))
        for slot_index in range(1, slot_count + 1):
            slot = CanonicalRosterSlot(
                slot_id=roster_slot_key(team_id, slot_type, slot_index),
                slot_type=slot_type,
                slot_index=slot_index,
                display_label=slot_display_label(slot_type, slot_index, slot_count),
                is_starter=slot_type not in {"BENCH", "IR"},
                is_ir=slot_type == "IR",
            )
            slots.append(slot)
            by_assignment_key[(slot_type, slot_index)] = slot

    for entry in sorted(roster_entries, key=lambda candidate: candidate.id or 0):
        slot_type = normalize_slot(entry.slot)
        if slot_type is None:
            raise RosterSlotIntegrityError(f"roster entry {entry.id} has unsupported slot {entry.slot!r}")
        slot_index = entry.slot_index
        if slot_index is None or slot_index < 1:
            raise RosterSlotIntegrityError(f"roster entry {entry.id} has no valid slot index")
        target = by_assignment_key.get((slot_type, slot_index))
        if target is None:
            raise RosterSlotIntegrityError(
                f"roster entry {entry.id} targets {slot_type}{slot_index}, which is not configured for team {team_id}"
            )
        if target.entry is not None:
            raise RosterSlotIntegrityError(
                f"roster entries {target.entry.id} and {entry.id} both target {slot_type}{slot_index}"
            )
        target.entry = entry
    return slots


def first_open_eligible_slot(
    team_id: int,
    player_position: str,
    roster_slots: Mapping[str, int] | None,
    roster_entries: list[RosterEntry],
    *,
    superflex_enabled: bool = False,
) -> tuple[str, int] | None:
    """Return the first configured empty slot a player may legally occupy."""
    slots = build_team_roster_slots(team_id, roster_slots, roster_entries)
    limits = normalize_roster_slot_limits(roster_slots)
    eligible_slot_types = eligible_slots_for_position(
        player_position,
        superflex_is_enabled(limits, configured=superflex_enabled),
    )
    for slot in slots:
        if slot.slot_type in eligible_slot_types and slot.entry is None:
            return slot.slot_type, slot.slot_index
    return None
