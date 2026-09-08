"""Authoritative cumulative positional fantasy ranks for player cards.

Ranks use verified weekly scoring rows from fantasy weeks whose application
matchups have all finalized.  A final, game-keyed box score is used only when
the corresponding weekly row is missing, so a completed performance is never
silently converted into zero points while the weekly import is repaired.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points
from collegefootballfantasy_api.app.services.fantasy_week_finality import (
    latest_authoritatively_finalized_week,
)
from collegefootballfantasy_api.app.services.fantasy_game_selection import (
    fantasy_games_by_school,
    fantasy_stat_weeks,
    school_key,
)
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
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
    return season_positional_ranks(db, position=player.position, season=season).get(player.id)


def season_positional_ranks(
    db: Session, *, position: str, season: int,
) -> dict[int, PlayerSeasonPositionalRank]:
    """Return a player's cumulative rank after a finalized fantasy week.

    The eligible player universe is the exact canonical public draft/waiver
    pool.  Within a position, ties are deterministically ordered by player
    name and id so every eligible player has one ordinal rank from 1 through
    the size of that position's pool.
    """

    through_week = min(latest_authoritatively_finalized_week(db, season=season), calendar_cfb_week(season) - 1)
    if through_week < 1:
        return {}

    position = (position or "").strip().upper()
    players = db.scalars(
        select(Player).where(
            canonical_fantasy_player_filter(season),
            Player.position == position,
        )
    ).all()
    if not players:
        return {}

    player_ids = tuple(candidate.id for candidate in players)
    position_by_player_id = {candidate.id: position for candidate in players}
    school_by_player_id = {candidate.id: candidate.school for candidate in players}
    totals = {player_id: 0.0 for player_id in player_ids}
    # A school with a completed Week 0 opener uses that one game as its
    # fantasy Week 1 score. Its later real-world Week 1 game remains visible
    # in player history, but cannot inflate the published positional rank.
    selected_stat_weeks_by_player = {player_id: set() for player_id in player_ids}
    selected_game_id_by_player_week: dict[tuple[int, int], int] = {}
    games = db.scalars(
        select(Game).where(
            Game.season == season,
            Game.week.in_(tuple(range(0, through_week + 1))),
        )
    ).all()
    for fantasy_week in range(1, through_week + 1):
        selected_weeks = fantasy_stat_weeks(
            db,
            season=season,
            week=fantasy_week,
            player_ids=set(player_ids),
            games=games,
            player_schools={candidate.id: candidate.school for candidate in players},
        )
        selected_games = fantasy_games_by_school(
            db,
            season=season,
            week=fantasy_week,
            games=games,
        )
        for player_id, stat_week in selected_weeks.items():
            selected_stat_weeks_by_player[player_id].add(stat_week)
            selected_game = selected_games.get(school_key(school_by_player_id[player_id]))
            if selected_game is not None and selected_game.week == stat_week:
                selected_game_id_by_player_week[player_id, stat_week] = selected_game.id

    candidate_stat_weeks = {
        week
        for weeks in selected_stat_weeks_by_player.values()
        for week in weeks
    }
    rows = db.scalars(
        select(PlayerStat).where(
            PlayerStat.player_id.in_(player_ids),
            PlayerStat.season == season,
            PlayerStat.week.in_(candidate_stat_weeks or {-1}),
            PlayerStat.verified.is_(True),
        )
    ).all()
    verified_stat_keys: set[tuple[int, int]] = set()
    for row in rows:
        if row.week not in selected_stat_weeks_by_player[row.player_id]:
            continue
        totals[row.player_id] += _fantasy_points(
            row.stats,
            position=position_by_player_id[row.player_id],
        )
        verified_stat_keys.add((row.player_id, row.week))

    # The live worker normally writes both records atomically.  Historical
    # recovery can legitimately restore the immutable final game row first.
    # Use that exact selected final game only while the weekly row is absent;
    # never add it to an existing weekly total or select a second real game.
    selected_game_ids = set(selected_game_id_by_player_week.values())
    fallback_rows = db.scalars(
        select(PlayerGameStat)
        .join(Game, Game.id == PlayerGameStat.game_id)
        .where(
            PlayerGameStat.player_id.in_(player_ids),
            PlayerGameStat.game_id.in_(selected_game_ids or {-1}),
            PlayerGameStat.season == season,
            Game.schedule_status.in_(("final", "post")),
        )
    ).all()
    fallback_by_player_game = {
        (row.player_id, row.game_id): row
        for row in fallback_rows
    }
    for (player_id, stat_week), game_id in selected_game_id_by_player_week.items():
        if (player_id, stat_week) in verified_stat_keys:
            continue
        fallback = fallback_by_player_game.get((player_id, game_id))
        if fallback is not None:
            totals[player_id] += _fantasy_points(
                fallback.stats,
                position=position_by_player_id[player_id],
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
    return {
        player_id: PlayerSeasonPositionalRank(
            position=position, rank=rank, fantasy_points=round(totals[player_id], 1), through_week=through_week,
        )
        for player_id, rank in rank_by_player_id.items()
    }
