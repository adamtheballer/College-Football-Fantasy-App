from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from api.app.models.game import Game
from api.app.models.league import League
from api.app.models.player import Player
from api.app.services.league_week_state import enforce_lineup_window_open, resolve_current_league_week


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def enforce_roster_window_open(db: Session, league: League) -> None:
    enforce_lineup_window_open(db, league=league)


def started_player_ids_for_week(
    db: Session,
    *,
    league: League,
    player_ids: set[int],
    season: int | None = None,
    week: int | None = None,
    now_utc: datetime | None = None,
) -> set[int]:
    if not player_ids:
        return set()

    resolved_season, resolved_week = (
        (season, week) if season is not None and week is not None else resolve_current_league_week(db, league=league)
    )
    now = _as_utc(now_utc) or datetime.now(timezone.utc)

    players = db.query(Player).filter(Player.id.in_(player_ids)).all()
    school_by_player_id = {player.id: (player.school or "").strip().upper() for player in players}
    schools = {school for school in school_by_player_id.values() if school}
    if not schools:
        return set()

    game_rows = (
        db.query(Game)
        .filter(Game.season == int(resolved_season), Game.week == int(resolved_week))
        .filter(or_(func.upper(Game.home_team).in_(schools), func.upper(Game.away_team).in_(schools)))
        .all()
    )
    locked_schools: set[str] = set()
    for game in game_rows:
        start = _as_utc(game.start_date)
        if start is None or start > now:
            continue
        locked_schools.add((game.home_team or "").strip().upper())
        locked_schools.add((game.away_team or "").strip().upper())

    return {player_id for player_id, school in school_by_player_id.items() if school in locked_schools}


def enforce_players_unlocked_for_week(
    db: Session,
    *,
    league: League,
    player_ids: set[int],
    action_label: str,
    season: int | None = None,
    week: int | None = None,
) -> None:
    locked_player_ids = started_player_ids_for_week(
        db,
        league=league,
        player_ids=player_ids,
        season=season,
        week=week,
    )
    if locked_player_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{action_label} blocked because one or more player games have started",
        )
