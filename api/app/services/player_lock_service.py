from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def game_starts_for_players(
    db: Session,
    *,
    player_ids: set[int],
    season: int,
    week: int,
) -> dict[int, datetime | None]:
    if not player_ids:
        return {}
    players = db.query(Player.id, Player.school).filter(Player.id.in_(player_ids)).all()
    schools = {school for _, school in players if school}
    if not schools:
        return {player_id: None for player_id in player_ids}
    games = (
        db.query(Game)
        .filter(
            Game.season == season,
            Game.week == week,
            Game.start_date.isnot(None),
            or_(Game.home_team.in_(schools), Game.away_team.in_(schools)),
        )
        .all()
    )
    starts_by_school: dict[str, datetime] = {}
    for game in games:
        if game.start_date is None:
            continue
        start = as_utc(game.start_date)
        for school in (game.home_team, game.away_team):
            if school in schools and (school not in starts_by_school or start < starts_by_school[school]):
                starts_by_school[school] = start
    return {player_id: starts_by_school.get(school) for player_id, school in players}


def locked_player_ids(
    db: Session,
    *,
    player_ids: set[int],
    season: int,
    week: int,
    now: datetime,
) -> set[int]:
    current = as_utc(now)
    starts = game_starts_for_players(db, player_ids=player_ids, season=season, week=week)
    return {player_id for player_id, start in starts.items() if start is not None and start <= current}


def is_player_locked(
    db: Session,
    *,
    player_id: int,
    season: int,
    week: int,
    now: datetime,
) -> bool:
    return player_id in locked_player_ids(
        db,
        player_ids={player_id},
        season=season,
        week=week,
        now=now,
    )
