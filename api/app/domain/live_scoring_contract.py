"""Fail-closed contracts for the live-scoring ingestion pipeline.

The legacy import shape normalized absent values to zero.  That is acceptable
for an explicitly complete box score, but unsafe for a partial provider
response.  This module preserves the distinction before any score can be
calculated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from collegefootballfantasy_api.app.domain.stat_normalization import aliases_for_position


COMPLETE = "complete"
INCOMPLETE = "incomplete"
VALID_COMPLETENESS = {COMPLETE, INCOMPLETE}
SCHEDULED = "scheduled"
PRE_GAME = "pre_game"
IN_PROGRESS = "in_progress"
HALFTIME = "halftime"
DELAYED = "delayed"
POSTPONED = "postponed"
SUSPENDED = "suspended"
CANCELED = "canceled"
FINAL_UNVERIFIED = "final_unverified"
FINAL_VERIFIED = "final_verified"
CORRECTED = "corrected"

VALID_GAME_LIFECYCLES = {
    SCHEDULED,
    PRE_GAME,
    IN_PROGRESS,
    HALFTIME,
    DELAYED,
    POSTPONED,
    SUSPENDED,
    CANCELED,
    FINAL_UNVERIFIED,
    FINAL_VERIFIED,
    CORRECTED,
    # Legacy aliases are accepted only for historical replay/import mapping.
    "live",
    "final",
}

VALID_LIFECYCLE_TRANSITIONS = {
    SCHEDULED: {PRE_GAME, POSTPONED, CANCELED},
    PRE_GAME: {IN_PROGRESS, DELAYED, POSTPONED, CANCELED},
    IN_PROGRESS: {HALFTIME, DELAYED, SUSPENDED, FINAL_UNVERIFIED},
    HALFTIME: {IN_PROGRESS, DELAYED, SUSPENDED, FINAL_UNVERIFIED},
    DELAYED: {IN_PROGRESS, POSTPONED, SUSPENDED, CANCELED},
    POSTPONED: {SCHEDULED, CANCELED},
    SUSPENDED: {IN_PROGRESS, POSTPONED, CANCELED, FINAL_UNVERIFIED},
    FINAL_UNVERIFIED: {FINAL_VERIFIED, CORRECTED},
    FINAL_VERIFIED: {CORRECTED},
    CORRECTED: {FINAL_UNVERIFIED, FINAL_VERIFIED},
    CANCELED: set(),
}


class LiveScoringContractError(ValueError):
    """A provider payload is not safe to promote into a score."""


class IncompleteStatRevisionError(LiveScoringContractError):
    """The provider did not declare a complete player stat revision."""


class InvalidStatValueError(LiveScoringContractError):
    """A provider sent a malformed value for a scoring stat."""


def validate_lifecycle_transition(current: str | None, proposed: str) -> None:
    """Reject impossible game-state transitions before a revision is accepted."""
    if proposed not in VALID_GAME_LIFECYCLES:
        raise LiveScoringContractError("invalid game lifecycle state")
    aliases = {"live": IN_PROGRESS, "final": FINAL_VERIFIED}
    normalized_current = aliases.get(current or "", current)
    normalized_proposed = aliases.get(proposed, proposed)
    if normalized_current is not None and normalized_proposed not in VALID_LIFECYCLE_TRANSITIONS.get(normalized_current, set()):
        raise LiveScoringContractError(f"invalid game lifecycle transition: {current} -> {proposed}")


@dataclass(frozen=True)
class StrictNormalizedStats:
    stats: dict[str, float | None]
    missing_keys: tuple[str, ...]
    completeness: str

    @property
    def scoreable(self) -> bool:
        return self.completeness == COMPLETE and not self.missing_keys

    def require_scoreable(self) -> dict[str, float]:
        if not self.scoreable:
            raise IncompleteStatRevisionError(
                "A live score requires an explicitly complete provider revision; "
                f"missing={','.join(self.missing_keys) or 'provider completeness declaration'}"
            )
        return {key: float(value) for key, value in self.stats.items() if value is not None}


def _lookup(raw_stats: Mapping[str, Any], aliases: list[str]) -> tuple[bool, Any]:
    for key in aliases:
        if key in raw_stats:
            return True, raw_stats[key]
    lowered = {str(key).lower(): value for key, value in raw_stats.items()}
    for key in aliases:
        if key.lower() in lowered:
            return True, lowered[key.lower()]
    return False, None


def normalize_live_stat_revision(
    raw_stats: Mapping[str, Any] | None,
    position: str | None,
    *,
    completeness: str,
) -> StrictNormalizedStats:
    """Normalize a provider revision without turning missing fields into zero.

    A provider may omit a zero-valued stat *only when it marks the complete
    player revision as complete*.  Partial revisions retain ``None`` and are
    blocked before they reach the scoring engine.
    """
    normalized_completeness = completeness.strip().lower()
    if normalized_completeness not in VALID_COMPLETENESS:
        raise LiveScoringContractError("completeness must be 'complete' or 'incomplete'")
    source = raw_stats or {}
    if not isinstance(source, Mapping):
        raise LiveScoringContractError("provider stats must be an object")

    stats: dict[str, float | None] = {}
    missing: list[str] = []
    for stat_key, aliases in aliases_for_position(position).items():
        found, value = _lookup(source, aliases)
        if not found or value is None or value == "":
            if normalized_completeness == COMPLETE:
                # Explicitly complete providers may omit a zero stat.
                stats[stat_key] = 0.0
            else:
                stats[stat_key] = None
                missing.append(stat_key)
            continue
        try:
            stats[stat_key] = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidStatValueError(f"invalid value for {stat_key}") from exc
    return StrictNormalizedStats(stats=stats, missing_keys=tuple(missing), completeness=normalized_completeness)
