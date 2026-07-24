from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.services.league_schedule import ensure_league_schedule
from collegefootballfantasy_api.app.services.roster_legality import assign_best_roster_slot_for_team

DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BENCH": 4,
    "IR": 1,
}


def finalize_draft_rosters_and_matchups(db: Session, league: League) -> dict[str, int]:
    db.flush()

    draft = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft:
        return {"rosters_backfilled": 0, "matchups_created": 0}

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    roster_slots = settings_row.roster_slots_json if settings_row else DEFAULT_ROSTER_SLOTS
    superflex_enabled = bool(settings_row.superflex_enabled) if settings_row else False

    picks = (
        db.query(DraftPick)
        .filter(DraftPick.draft_id == draft.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )

    rosters_backfilled = 0
    for pick in picks:
        existing = (
            db.query(RosterEntry)
            .filter(RosterEntry.league_id == league.id, RosterEntry.player_id == pick.player_id)
            .first()
        )
        if existing:
            continue

        player = db.get(Player, pick.player_id)
        if not player:
            continue

        slot = assign_best_roster_slot_for_team(
            db,
            pick.team_id,
            player.position,
            roster_slots,
            superflex_enabled=superflex_enabled,
        )
        if slot is None:
            raise RuntimeError("draft roster backfill found no legal slot for a drafted player")
        db.add(
            RosterEntry(
                league_id=league.id,
                team_id=pick.team_id,
                player_id=pick.player_id,
                slot=slot,
                status="active",
            )
        )
        rosters_backfilled += 1

    if rosters_backfilled:
        db.flush()

    matchups_created = ensure_league_schedule(db, league)
    if draft.status == "completed":
        league.status = "post_draft"
        db.add(league)
        # Waiver order and FAAB balances derive only from this finalized official
        # draft order. Mock or incomplete drafts never enter this path.
        from collegefootballfantasy_api.app.services.waiver_service import (
            initialize_waiver_state_after_official_draft,
        )

        initialize_waiver_state_after_official_draft(db, league)

    return {"rosters_backfilled": rosters_backfilled, "matchups_created": matchups_created}
