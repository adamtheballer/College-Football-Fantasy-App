"""Authoritative cumulative positional fantasy ranks for player cards.

Ranks intentionally use only verified PlayerStat rows from fantasy weeks whose
application matchups have all finalized.  This keeps a player card from
showing a misleading partial rank while games or official corrections are
still in progress.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points
from collegefootballfantasy_api.app.services.fantasy_week_finality import (
    latest_authoritatively_finalized_week,
)
from collegefootballfantasy_api.app.services.player_pool_filters import (
    canonical_fantasy_player_filter,
)


@dataclass(frozen=True)
class PlayerSeasonPositionalRank:
    """A stable rank published after completed fantasy weeks only."""

    position: str
    rank: int
    fantasy_points: float
    through_week: int


def _fantasy_points(stats: dict | None, *, position: str) -> float:
    if not stats:
        return 0.0
    for key in ("fantasy_points", "fantasyPoints", "fpts"):
        value = stats.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return calculate_fantasy_points(stats, position=position)


def season_positional_rank_for_player(
    db: Session,
    *,
    player: Player,
    season: int,
) -> PlayerSeasonPositionalRank | None:
    """Return a player's cumulative rank after a finalized fantasy week.

    The eligible player universe is the exact canonical public draft/waiver
    pool.  Within a position, ties are deterministically ordered by player
    name and id so every eligible player has one ordinal rank from 1 through
    the size of that position's pool.
    """

    through_week = latest_authoritatively_finalized_week(db, season=season)
    if through_week < 1:
        return None

    position = (player.position or "").strip().upper()
    players = db.scalars(
        select(Player).where(
            canonical_fantasy_player_filter(season),
            Player.position == position,
        )
    ).all()
    if not players or player.id not in {candidate.id for candidate in players}:
        return None

    player_ids = tuple(candidate.id for candidate in players)
    position_by_player_id = {candidate.id: position for candidate in players}
    totals = {player_id: 0.0 for player_id in player_ids}
    rows = db.scalars(
        select(PlayerStat).where(
            PlayerStat.player_id.in_(player_ids),
            PlayerStat.season == season,
            PlayerStat.week.between(1, through_week),
            PlayerStat.verified.is_(True),
        )
    ).all()
    for row in rows:
        totals[row.player_id] += _fantasy_points(
            row.stats,
            position=position_by_player_id[row.player_id],
        )

    ordered = sorted(
        players,
        key=lambda candidate: (
            -totals[candidate.id],
            candidate.name.casefold(),
            candidate.id,
        ),
    )
    rank_by_player_id = {
        candidate.id: rank
        for rank, candidate in enumerate(ordered, start=1)
    }
    return PlayerSeasonPositionalRank(
        position=position,
        rank=rank_by_player_id[player.id],
        fantasy_points=round(totals[player.id], 1),
        through_week=through_week,
    )
