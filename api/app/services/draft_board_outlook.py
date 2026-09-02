"""Authoritative rest-of-season inputs for real and mock draft boards.

The board must stop treating a preseason total as current once verified games
are available.  This service combines the published remaining-week snapshots
with a conservative, bounded form adjustment for future untouched preseason
rows.  It is read-only: the weekly outlook worker remains the only publisher
of projection snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.projection import (
    current_published_projections_for_weeks_query,
)
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points
from collegefootballfantasy_api.app.services.player_pool_filters import (
    canonical_fantasy_player_filter,
)
from collegefootballfantasy_api.app.services.weekly_outlook_refresh import (
    POSTGAME_MODEL_VERSION,
    POSTGAME_PROJECTION_VERSION,
)

MAX_REGULAR_SEASON_WEEK = 13
MAX_FORM_WEIGHT = 0.35
FORM_WEIGHT_PER_VERIFIED_GAME = 0.08


@dataclass(frozen=True)
class DraftBoardOutlook:
    projected_points: float
    rank: int
    completed_week: int
    updated_at: datetime | None


def _fantasy_points(stats: dict | None, *, position: str) -> float | None:
    if not stats:
        return None
    for key in ("fantasy_points", "fantasyPoints", "fpts"):
        value = stats.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    # Provider stat payloads usually contain raw box-score categories rather
    # than a precomputed fantasy total.  Normalize them through the same
    # default scoring engine used by weekly projections instead of silently
    # ignoring a real result.
    return calculate_fantasy_points(stats, position=position)


def _latest_completed_week(db: Session, *, season: int) -> int:
    """Use the post-final publisher as the board's completion authority.

    Raw provider stats can be partial or corrected.  A MIDWEEK postgame
    snapshot for Week N+1 exists only after the scoring worker has certified
    Week N, which is exactly when draft rankings may react to that result.
    """

    next_week = db.scalar(
        select(func.max(WeeklyProjection.week)).where(
            WeeklyProjection.season == season,
            WeeklyProjection.projection_version == POSTGAME_PROJECTION_VERSION,
            WeeklyProjection.model_version == POSTGAME_MODEL_VERSION,
            WeeklyProjection.is_published.is_(True),
        )
    )
    if next_week is None:
        return 0
    return max(0, min(int(next_week) - 1, MAX_REGULAR_SEASON_WEEK))


def _fallback_weekly_projection(player: Player) -> float:
    season_total = float(player.sheet_projected_season_points or 0.0)
    return max(0.0, season_total / 12.0)


def build_rest_of_season_draft_board(
    db: Session,
    *,
    season: int,
) -> dict[int, DraftBoardOutlook]:
    """Calculate the current master-board rest-of-season totals and ranks.

    Published future projections are the primary source.  For untouched
    PRESEASON weeks only, verified prior results apply a capped adjustment.
    Thus an outlier (such as a player falling 14 points short one week) moves
    the board, but cannot turn one game into an unjustified collapse.
    """

    players = db.scalars(
        select(Player).where(canonical_fantasy_player_filter(season))
    ).all()
    if not players:
        return {}

    completed_week = _latest_completed_week(db, season=season)
    future_weeks = tuple(range(completed_week + 1, MAX_REGULAR_SEASON_WEEK + 1))
    observed_weeks = tuple(range(1, completed_week + 1))
    all_weeks = tuple((*observed_weeks, *future_weeks))
    projections_by_player_week = {
        (row.player_id, row.week): row
        for row in db.scalars(
            current_published_projections_for_weeks_query(
                season=season,
                weeks=all_weeks,
                player_ids=tuple(player.id for player in players),
            )
        ).all()
    }
    position_by_player_id = {player.id: player.position for player in players}
    actual_by_player_week = {
        (row.player_id, row.week): points
        for row in db.scalars(
            select(PlayerStat).where(
                PlayerStat.season == season,
                PlayerStat.verified.is_(True),
                PlayerStat.week.in_(observed_weeks or (0,)),
                PlayerStat.player_id.in_(position_by_player_id),
            )
        ).all()
        if (points := _fantasy_points(row.stats, position=position_by_player_id.get(row.player_id, ""))) is not None
    }

    totals: list[tuple[Player, float, datetime | None]] = []
    for player in players:
        fallback_weekly = _fallback_weekly_projection(player)
        future_total = 0.0
        untouched_preseason_weeks = 0
        latest_updated_at: datetime | None = None
        for week in future_weeks:
            projection = projections_by_player_week.get((player.id, week))
            if projection is None:
                future_total += fallback_weekly
                untouched_preseason_weeks += 1
                continue
            future_total += max(0.0, float(projection.fantasy_points or 0.0))
            if projection.projection_version == "PRESEASON":
                untouched_preseason_weeks += 1
            if latest_updated_at is None or projection.updated_at > latest_updated_at:
                latest_updated_at = projection.updated_at

        residuals: list[float] = []
        for week in observed_weeks:
            actual = actual_by_player_week.get((player.id, week))
            projection = projections_by_player_week.get((player.id, week))
            if actual is None or projection is None:
                continue
            expected = max(4.0, float(projection.fantasy_points or 0.0))
            # One anomalous score cannot dominate every remaining week.
            residuals.append(max(-expected, min(expected, actual - expected)))

        form_adjustment = 0.0
        if residuals and untouched_preseason_weeks:
            form_weight = min(MAX_FORM_WEIGHT, FORM_WEIGHT_PER_VERIFIED_GAME * len(residuals))
            form_adjustment = (sum(residuals) / len(residuals)) * form_weight * untouched_preseason_weeks

        totals.append((player, round(max(0.0, future_total + form_adjustment), 1), latest_updated_at))

    ordered = sorted(
        totals,
        key=lambda item: (-item[1], item[0].position, item[0].name.casefold(), item[0].id),
    )
    return {
        player.id: DraftBoardOutlook(
            projected_points=projected_points,
            rank=rank,
            completed_week=completed_week,
            updated_at=updated_at,
        )
        for rank, (player, projected_points, updated_at) in enumerate(ordered, start=1)
    }
