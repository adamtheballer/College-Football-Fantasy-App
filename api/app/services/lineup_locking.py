from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.scoring_engine import is_starting_slot
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.services.team_provider_mapping import games_for_player_school


def _now() -> datetime:
    return datetime.now(timezone.utc)


def player_is_locked_for_week(
    db: Session,
    *,
    player: Player,
    season: int,
    week: int,
    now: datetime,
) -> bool:
    games = games_for_player_school(db, player=player, season=season, week=week)
    for game in games:
        start_date = game.start_date
        if start_date is None:
            continue
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if start_date <= now:
            return True
    return False


def create_or_refresh_lineup_snapshots(db: Session, league_id: int, season: int, week: int) -> int:
    existing_by_player = {
        snapshot.player_id: snapshot
        for snapshot in db.query(LineupWeekSnapshot)
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
        )
        .all()
    }
    roster_entries = (
        db.query(RosterEntry)
        .filter(RosterEntry.league_id == league_id)
        .order_by(RosterEntry.team_id.asc(), RosterEntry.id.asc())
        .all()
    )
    players_by_id = {
        player.id: player
        for player in db.query(Player)
        .filter(Player.id.in_({entry.player_id for entry in roster_entries} or {0}))
        .all()
    }
    locked_at = _now()
    changed = 0
    for entry in roster_entries:
        snapshot = existing_by_player.get(entry.player_id)
        player = players_by_id.get(entry.player_id)
        player_locked = bool(
            player
            and player_is_locked_for_week(db, player=player, season=season, week=week, now=locked_at)
        )
        if snapshot and player_locked:
            continue
        if not snapshot:
            snapshot = LineupWeekSnapshot(
                league_id=league_id,
                team_id=entry.team_id,
                player_id=entry.player_id,
                season=season,
                week=week,
                slot=(entry.slot or "BENCH").upper(),
                is_starter=is_starting_slot(entry.slot or ""),
                locked_at=locked_at,
            )
            db.add(snapshot)
            changed += 1
            continue
        snapshot.team_id = entry.team_id
        snapshot.slot = (entry.slot or "BENCH").upper()
        snapshot.is_starter = is_starting_slot(entry.slot or "")
        snapshot.locked_at = locked_at
        changed += 1
    if changed:
        db.flush()
    return changed
