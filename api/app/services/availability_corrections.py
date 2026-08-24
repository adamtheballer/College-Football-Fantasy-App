"""Shared safeguards for verified player-availability corrections.

Official conference reports are the default source of truth.  A reviewed team
report can temporarily supersede them when it is newer or more specific, but
only inside its explicit week window.  This keeps a one-off correction from
being overwritten by stale provider data without creating a permanent manual
state.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


MANUAL_VERIFIED_SOURCE = "manual_verified_team_report"
CORRECTION_VERSION = "CORRECTED_INJURY"
CORRECTION_MODEL_VERSION = "injury_override_v1"

_ZERO_COLUMNS = (
    "pass_attempts", "rush_attempts", "targets", "receptions", "expected_plays",
    "expected_rush_per_play", "expected_td_per_play", "pass_yards", "rush_yards",
    "rec_yards", "pass_tds", "rush_tds", "rec_tds", "interceptions",
    "field_goals_made_0_to_39", "field_goals_made_40_to_49", "field_goals_made_0_to_49",
    "field_goals_made_50_plus", "extra_points_made", "fantasy_points", "floor", "ceiling",
    "boom_prob", "bust_prob",
)


def has_active_manual_override(db: Session, *, player_id: int, season: int, week: int) -> bool:
    """Whether a reviewed, bounded team-report correction controls this week."""
    return db.scalar(
        select(PlayerAvailabilityEvent.id).where(
            PlayerAvailabilityEvent.player_id == player_id,
            PlayerAvailabilityEvent.season == season,
            PlayerAvailabilityEvent.source == MANUAL_VERIFIED_SOURCE,
            PlayerAvailabilityEvent.reviewed.is_(True),
            PlayerAvailabilityEvent.effective_from_week <= week,
            (PlayerAvailabilityEvent.effective_until_week.is_(None))
            | (PlayerAvailabilityEvent.effective_until_week >= week),
        ).limit(1)
    ) is not None


def publish_zero_projection_for_unavailable_player(
    db: Session,
    *,
    player: Player,
    season: int,
    week: int,
    status: str,
    note: str,
) -> WeeklyProjection | None:
    """Publish a zero projection for a confirmed OUT/IR player.

    The original projection is retained.  Read paths rank this correction above
    provider snapshots, so every roster, matchup, waiver, and player endpoint
    receives the same zero result.
    """
    if status not in {"OUT", "IR"}:
        return None

    source = db.scalar(
        current_published_projections_query(
            season=season, week=week, player_ids=(player.id,)
        )
    )
    if source is None:
        return None

    correction = db.scalar(
        select(WeeklyProjection).where(
            WeeklyProjection.player_id == player.id,
            WeeklyProjection.season == season,
            WeeklyProjection.week == week,
            WeeklyProjection.projection_version == CORRECTION_VERSION,
        )
    )
    if correction is None:
        correction = WeeklyProjection(
            player_id=player.id,
            season=season,
            week=week,
            projection_version=CORRECTION_VERSION,
            team_id=source.team_id,
            opponent_team_id=source.opponent_team_id,
            neutral_baseline=source.neutral_baseline,
            baseline_games_played=source.baseline_games_played,
            baseline_source="verified_availability_correction",
        )
        db.add(correction)

    for column in _ZERO_COLUMNS:
        setattr(correction, column, 0.0)
    correction.qb_rating = None
    correction.projection_status = status
    correction.availability_multiplier = 0.0
    correction.usage_multiplier = 1.0
    correction.offense_multiplier = 1.0
    correction.opponent_defense_multiplier = 1.0
    correction.confidence = 1.0
    correction.fallback_reason = note[:500]
    correction.model_version = CORRECTION_MODEL_VERSION
    correction.is_published = True
    correction.locked_at = None
    return correction
