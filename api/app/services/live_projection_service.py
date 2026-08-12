"""Pure live-projection math for the shadow ESPN scoring pipeline.

The provider supplies the points already earned.  The published weekly
projection remains the estimate for the portion of the game that has not yet
been played.  Keeping this calculation pure makes it testable and prevents a
partial box score from overwriting a pre-game projection or public score.
"""

from __future__ import annotations

from typing import Any

from collegefootballfantasy_api.app.domain.live_scoring_contract import (
    CORRECTED,
    FINAL_UNVERIFIED,
    FINAL_VERIFIED,
    HALFTIME,
    IN_PROGRESS,
)


_FINAL_STATES = {FINAL_UNVERIFIED, FINAL_VERIFIED, CORRECTED, "final"}
_ACTIVE_STATES = {IN_PROGRESS, HALFTIME, "live"}


def _clock_seconds(value: object) -> int | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    minutes, seconds = value.split(":", 1)
    try:
        parsed = int(minutes) * 60 + int(seconds)
    except ValueError:
        return None
    return parsed if 0 <= parsed <= 15 * 60 else None


def _status_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Find ESPN's status object in either scoreboard or summary payloads."""
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("status"), dict):
        return payload["status"]
    header = payload.get("header")
    if isinstance(header, dict):
        competitions = header.get("competitions")
        if isinstance(competitions, list) and competitions and isinstance(competitions[0], dict):
            status = competitions[0].get("status")
            if isinstance(status, dict):
                return status
        status = header.get("status")
        if isinstance(status, dict):
            return status
    return {}


def game_progress_fraction(*, lifecycle_state: str, provider_payload: dict[str, Any] | None) -> float:
    """Return the completed fraction of regulation play, bounded to [0, 1].

    ESPN reports ``period`` and a remaining ``displayClock`` for in-progress
    games.  If a provider omits that timing detail, use a conservative midpoint
    fallback instead of treating a live player as pre-game or final.
    """
    if lifecycle_state in _FINAL_STATES:
        return 1.0
    if lifecycle_state == HALFTIME:
        return 0.5
    if lifecycle_state not in _ACTIVE_STATES:
        return 0.0

    status = _status_payload(provider_payload)
    period = status.get("period")
    try:
        period_number = int(period)
    except (TypeError, ValueError):
        period_number = 0
    remaining = _clock_seconds(status.get("displayClock"))
    if period_number >= 5:
        # Overtime is real game time, but projecting extra remaining regulation
        # would inflate the estimate.  Treat it as effectively complete until
        # the final box score arrives.
        return 0.99
    if 1 <= period_number <= 4 and remaining is not None:
        elapsed_in_period = 15 * 60 - remaining
        return max(0.0, min(0.99, ((period_number - 1) * 15 * 60 + elapsed_in_period) / (4 * 15 * 60)))
    return 0.5


def live_projected_points(
    *,
    pre_game_projection: float | None,
    actual_points: float | None,
    lifecycle_state: str | None,
    provider_payload: dict[str, Any] | None,
) -> tuple[float | None, str, float]:
    """Blend score-to-date with the unplayed part of the published forecast.

    A player who underperforms early has a lower projected finish; a player
    exceeding the published pace has a higher one.  At final, the projection
    is the actual fantasy total and the pre-game value remains separately
    available for presentation beneath it.
    """
    state = lifecycle_state or "scheduled"
    progress = game_progress_fraction(lifecycle_state=state, provider_payload=provider_payload)
    if actual_points is None:
        return pre_game_projection, "pre_game", progress
    if state in _FINAL_STATES:
        return actual_points, "actual", progress
    if pre_game_projection is None:
        return actual_points, "live_actual_only", progress
    if state in _ACTIVE_STATES:
        return actual_points + pre_game_projection * (1.0 - progress), "live_pace_adjusted", progress
    return pre_game_projection, "pre_game", progress
