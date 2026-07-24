from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _school_schedule_key(school: str | None) -> str | None:
    if not school:
        return None
    return canonical_school_name(school) or normalize_school(school)


def game_context_for_players(
    db: Session,
    *,
    player_ids: set[int],
    season: int,
    week: int,
    player_schools: dict[int, str | None] | None = None,
) -> tuple[dict[int, datetime | None], dict[int, str | None]]:
    if not player_ids:
        return {}, {}
    if player_schools is None:
        player_schools = {
            player_id: school
            for player_id, school in db.query(Player.id, Player.school).filter(Player.id.in_(player_ids)).all()
        }
    school_keys = {
        key
        for school in player_schools.values()
        if (key := _school_schedule_key(school))
    }
    if not school_keys:
        empty = {player_id: None for player_id in player_ids}
        return empty, empty.copy()

    games = db.query(Game).filter(Game.season == season, Game.week == week).all()
    starts_by_school: dict[str, datetime] = {}
    opponents_by_school: dict[str, str] = {}
    for game in games:
        home_key = _school_schedule_key(game.home_team)
        away_key = _school_schedule_key(game.away_team)
        if home_key in school_keys:
            if away_key:
                opponents_by_school.setdefault(home_key, game.away_team)
            if game.start_date is not None:
                start = as_utc(game.start_date)
                if home_key not in starts_by_school or start < starts_by_school[home_key]:
                    starts_by_school[home_key] = start
        if away_key in school_keys:
            if home_key:
                opponents_by_school.setdefault(away_key, game.home_team)
            if game.start_date is not None:
                start = as_utc(game.start_date)
                if away_key not in starts_by_school or start < starts_by_school[away_key]:
                    starts_by_school[away_key] = start

    player_school_keys = {
        player_id: _school_schedule_key(player_schools.get(player_id))
        for player_id in player_ids
    }
    return (
        {
            player_id: starts_by_school.get(player_school_keys[player_id])
            for player_id in player_ids
        },
        {
            player_id: opponents_by_school.get(player_school_keys[player_id])
            for player_id in player_ids
        },
    )


def game_starts_for_players(
    db: Session,
    *,
    player_ids: set[int],
    season: int,
    week: int,
    player_schools: dict[int, str | None] | None = None,
) -> dict[int, datetime | None]:
    starts, _opponents = game_context_for_players(
        db,
        player_ids=player_ids,
        season=season,
        week=week,
        player_schools=player_schools,
    )
    return starts


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
