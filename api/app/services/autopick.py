from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.draft_queue_entry import DraftQueueEntry
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.roster_legality import assign_best_roster_slot_for_team


def _is_player_available(db: Session, draft: Draft, league_id: int, player_id: int) -> bool:
    drafted = (
        db.query(DraftPick.id)
        .filter(DraftPick.draft_id == draft.id, DraftPick.player_id == player_id)
        .first()
    )
    if drafted:
        return False
    rostered = (
        db.query(RosterEntry.id)
        .filter(RosterEntry.league_id == league_id, RosterEntry.player_id == player_id)
        .first()
    )
    return rostered is None


def queued_autopick_candidate(
    db: Session,
    *,
    draft: Draft,
    league_id: int,
    team: Team,
    roster_slots: dict,
    superflex_enabled: bool,
) -> Player | None:
    queue_rows = (
        db.query(DraftQueueEntry)
        .filter(DraftQueueEntry.draft_id == draft.id, DraftQueueEntry.team_id == team.id)
        .order_by(DraftQueueEntry.priority.asc(), DraftQueueEntry.id.asc())
        .all()
    )
    for queue_row in queue_rows:
        player = db.get(Player, queue_row.player_id)
        if not player or not _is_player_available(db, draft, league_id, player.id):
            continue
        if assign_best_roster_slot_for_team(
            db,
            team.id,
            player.position,
            roster_slots,
            superflex_enabled=superflex_enabled,
        ):
            return player
    return None


def best_available_autopick_candidate(
    db: Session,
    *,
    draft: Draft,
    league_id: int,
    team: Team,
    roster_slots: dict,
    superflex_enabled: bool,
) -> Player | None:
    players = db.query(Player).order_by(Player.id.asc()).all()
    for player in players:
        if not _is_player_available(db, draft, league_id, player.id):
            continue
        if assign_best_roster_slot_for_team(
            db,
            team.id,
            player.position,
            roster_slots,
            superflex_enabled=superflex_enabled,
        ):
            return player
    return None
