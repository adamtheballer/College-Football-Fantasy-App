from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.watchlist import Watchlist, WatchlistPlayer
from collegefootballfantasy_api.app.schemas.player import PlayerAvailabilityRead
from collegefootballfantasy_api.app.services.roster_lock_service import RosterLockError, ensure_player_unlocked


@dataclass(frozen=True)
class PlayerAvailabilityContext:
    roster_by_player: dict[int, RosterEntry]
    team_names_by_id: dict[int, str]
    drafted_player_ids: set[int]
    watchlisted_player_ids: set[int]


def build_availability_context(
    db: Session,
    *,
    league_id: int | None,
    current_user: User | None,
) -> PlayerAvailabilityContext:
    roster_by_player: dict[int, RosterEntry] = {}
    team_names_by_id: dict[int, str] = {}
    drafted_player_ids: set[int] = set()
    watchlisted_player_ids: set[int] = set()
    if league_id is None:
        return PlayerAvailabilityContext(roster_by_player, team_names_by_id, drafted_player_ids, watchlisted_player_ids)

    roster_rows = db.query(RosterEntry).filter(RosterEntry.league_id == league_id).all()
    roster_by_player = {row.player_id: row for row in roster_rows}
    team_names_by_id = {
        row.id: row.name
        for row in db.query(Team).filter(Team.league_id == league_id).all()
    }
    drafted_player_ids = {
        row[0]
        for row in db.query(DraftPick.player_id)
        .join(Draft, Draft.id == DraftPick.draft_id)
        .filter(Draft.league_id == league_id, DraftPick.player_id.is_not(None))
        .all()
    }
    if current_user is not None:
        watchlisted_player_ids = {
            row[0]
            for row in db.query(WatchlistPlayer.player_id)
            .join(Watchlist, Watchlist.id == WatchlistPlayer.watchlist_id)
            .filter(
                Watchlist.user_id == current_user.id,
                (Watchlist.league_id == league_id) | (Watchlist.league_id.is_(None)),
            )
            .all()
        }
    return PlayerAvailabilityContext(roster_by_player, team_names_by_id, drafted_player_ids, watchlisted_player_ids)


def _is_locked(db: Session, league: League | None, player: Player) -> bool:
    if league is None:
        return False
    try:
        ensure_player_unlocked(db, league, player)
    except RosterLockError:
        return True
    return False


def player_availability(
    db: Session,
    *,
    player: Player,
    league: League | None,
    context: PlayerAvailabilityContext,
) -> PlayerAvailabilityRead:
    league_id = league.id if league else None
    roster_entry = context.roster_by_player.get(player.id)
    if roster_entry:
        return PlayerAvailabilityRead(
            status="owned",
            league_id=league_id,
            team_id=roster_entry.team_id,
            team_name=context.team_names_by_id.get(roster_entry.team_id),
            roster_entry_id=roster_entry.id,
            roster_slot=roster_entry.slot,
            locked=_is_locked(db, league, player),
            drafted=player.id in context.drafted_player_ids,
            watchlisted=player.id in context.watchlisted_player_ids,
        )
    if player.id in context.drafted_player_ids:
        return PlayerAvailabilityRead(
            status="drafted",
            league_id=league_id,
            drafted=True,
            locked=_is_locked(db, league, player),
            watchlisted=player.id in context.watchlisted_player_ids,
        )
    if league is not None and _is_locked(db, league, player):
        return PlayerAvailabilityRead(
            status="locked",
            league_id=league_id,
            locked=True,
            watchlisted=player.id in context.watchlisted_player_ids,
        )
    return PlayerAvailabilityRead(
        status="free_agent",
        league_id=league_id,
        watchlisted=player.id in context.watchlisted_player_ids,
    )


def ownership_percentage(db: Session, player_id: int, *, season_year: int | None = None) -> float:
    league_query = db.query(League.id)
    if season_year is not None:
        league_query = league_query.filter(League.season_year == season_year)
    league_ids = [row[0] for row in league_query.all()]
    if not league_ids:
        return 0.0
    owned_count = (
        db.query(RosterEntry.league_id)
        .filter(RosterEntry.league_id.in_(league_ids), RosterEntry.player_id == player_id)
        .distinct()
        .count()
    )
    return round((owned_count / len(league_ids)) * 100, 2)
