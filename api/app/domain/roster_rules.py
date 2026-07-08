from __future__ import annotations

from dataclasses import dataclass

SCORING_SLOTS = {"QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K"}
NON_SCORING_SLOTS = {"BENCH", "IR"}
SUPPORTED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


class RosterRuleError(ValueError):
    pass


@dataclass(frozen=True)
class RosterSlotCheck:
    slot: str
    position: str


def normalize_slot(slot: str | None) -> str:
    normalized = (slot or "").strip().upper()
    if normalized == "BE":
        normalized = "BENCH"
    if not normalized:
        raise RosterRuleError("roster slot is required")
    return normalized


def normalize_position(position: str | None) -> str:
    normalized = (position or "").strip().upper()
    if normalized not in SUPPORTED_POSITIONS:
        raise RosterRuleError(f"unsupported player position: {normalized or 'unknown'}")
    return normalized


def validate_known_slot(slot: str, slot_limits: dict[str, int]) -> str:
    normalized = normalize_slot(slot)
    if normalized not in slot_limits:
        raise RosterRuleError(f"invalid roster slot: {normalized}")
    return normalized


def validate_slot_for_position(slot: str, position: str) -> RosterSlotCheck:
    normalized_slot = normalize_slot(slot)
    normalized_position = normalize_position(position)
    if normalized_slot in {"BENCH", "IR"}:
        return RosterSlotCheck(slot=normalized_slot, position=normalized_position)
    if normalized_slot == normalized_position:
        return RosterSlotCheck(slot=normalized_slot, position=normalized_position)
    if normalized_slot == "FLEX" and normalized_position in {"RB", "WR", "TE"}:
        return RosterSlotCheck(slot=normalized_slot, position=normalized_position)
    if normalized_slot == "SUPERFLEX" and normalized_position in {"QB", "RB", "WR", "TE"}:
        return RosterSlotCheck(slot=normalized_slot, position=normalized_position)
    raise RosterRuleError(f"{normalized_position} cannot be placed in {normalized_slot}")


def is_scoring_slot(slot: str | None) -> bool:
    return normalize_slot(slot) in SCORING_SLOTS
