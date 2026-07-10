from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.team_provider_mapping import games_for_player_school

FINAL_MATCHUP_STATUSES = {"final", "stat_corrected"}


class RosterLockError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def active_scoring_week(db: Session, league: League) -> int | None:
    row = (
        db.query(Matchup.week)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            ~Matchup.status.in_(FINAL_MATCHUP_STATUSES),
        )
        .order_by(Matchup.week.asc())
        .first()
    )
    return int(row[0]) if row else None


def player_lock_game(db: Session, league: League, player: Player, now: datetime | None = None) -> Game | None:
    timestamp = _aware(now or _now())

    week = active_scoring_week(db, league)
    weeks = [week] if week is not None else sorted({row[0] for row in db.query(Game.week).filter(Game.season == league.season_year).all()})
    for scoring_week in weeks:
        for game in games_for_player_school(db, player=player, season=league.season_year, week=scoring_week):
            if game.start_date and _aware(game.start_date) <= timestamp:
                return game
    return None


def is_player_locked(db: Session, league: League, player: Player, now: datetime | None = None) -> bool:
    return player_lock_game(db, league, player, now) is not None


def ensure_player_unlocked(db: Session, league: League, player: Player, now: datetime | None = None) -> None:
    game = player_lock_game(db, league, player, now)
    if game:
        raise RosterLockError(
            f"{player.name} is locked because {player.school} kicked off for week {game.week}"
        )
