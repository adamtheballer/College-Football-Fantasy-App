"""Single append-only ledger for meaningful league-specific player lifecycle events."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_player_event import LeaguePlayerEvent
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_waiver_availability import PlayerWaiverAvailability
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.player_trade_value import current_trade_value_snapshot
from collegefootballfantasy_api.app.schemas.league_player_history import (
    LeaguePlayerCurrentStatus,
    LeaguePlayerHistoryEvent,
    LeaguePlayerHistoryManager,
    LeaguePlayerHistoryRead,
    LeaguePlayerHistoryTeam,
)

EVENT_DRAFTED = "DRAFTED"
EVENT_AUTO_DRAFTED = "AUTO_DRAFTED"
EVENT_FREE_AGENT_ADDED = "FREE_AGENT_ADDED"
EVENT_WAIVER_CLAIMED = "WAIVER_CLAIMED"
EVENT_DROPPED = "DROPPED"
EVENT_PLACED_ON_WAIVERS = "PLACED_ON_WAIVERS"
EVENT_TRADED = "TRADED"
EVENT_TRADE_REVERSED = "TRADE_REVERSED"
EVENT_TRADE_FAILED = "TRADE_FAILED"
EVENT_PLACED_ON_IR = "PLACED_ON_IR"
EVENT_ACTIVATED_FROM_IR = "ACTIVATED_FROM_IR"
EVENT_COMMISSIONER_ADJUSTMENT = "COMMISSIONER_ADJUSTMENT"
EVENT_ROSTER_RELEASED = "ROSTER_RELEASED"


def _utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _manager_name(manager: User | None, team: Team | None) -> str | None:
    if manager:
        # User keeps a single display-name field in this application.  Avoid
        # assuming a provider-style last_name column in a write-path snapshot.
        return manager.first_name or manager.email
    return team.owner_name if team else None


def append_league_player_event(
    db: Session,
    *,
    league: League,
    player: Player,
    event_type: str,
    event_key: str,
    occurred_at: datetime | None = None,
    fantasy_team: Team | None = None,
    from_team: Team | None = None,
    to_team: Team | None = None,
    manager: User | None = None,
    draft_id: int | None = None,
    draft_pick_id: int | None = None,
    trade_id: int | None = None,
    waiver_claim_id: int | None = None,
    transaction_id: int | None = None,
    metadata: dict | None = None,
) -> LeaguePlayerEvent:
    """Append after the ownership mutation, before the enclosing transaction commits.

    A uniqueness key makes worker retries and historical backfills harmless.  Callers
    never commit here: a failed ownership transaction rolls the event back with it.
    """
    existing = (
        db.query(LeaguePlayerEvent)
        .filter(LeaguePlayerEvent.league_id == league.id, LeaguePlayerEvent.event_key == event_key)
        .one_or_none()
    )
    if existing:
        return existing
    chosen_team = fantasy_team or to_team or from_team
    chosen_manager = manager or (db.get(User, chosen_team.owner_user_id) if chosen_team and chosen_team.owner_user_id else None)
    row = LeaguePlayerEvent(
        league_id=league.id,
        season=league.season_year,
        player_id=player.id,
        event_type=event_type,
        event_key=event_key,
        occurred_at=_utc(occurred_at),
        fantasy_team_id=chosen_team.id if chosen_team else None,
        from_fantasy_team_id=from_team.id if from_team else None,
        to_fantasy_team_id=to_team.id if to_team else None,
        manager_user_id=chosen_manager.id if chosen_manager else None,
        draft_id=draft_id,
        draft_pick_id=draft_pick_id,
        trade_id=trade_id,
        waiver_claim_id=waiver_claim_id,
        transaction_id=transaction_id,
        player_name_snapshot=player.name,
        position_snapshot=player.position,
        school_snapshot=player.school,
        player_value_snapshot=(current_trade_value_snapshot(db, player_id=player.id, season=league.season_year) or {}).get("value", player.sheet_projected_season_points),
        fantasy_team_name_snapshot=chosen_team.name if chosen_team else None,
        from_team_name_snapshot=from_team.name if from_team else None,
        to_team_name_snapshot=to_team.name if to_team else None,
        manager_name_snapshot=_manager_name(chosen_manager, chosen_team),
        event_metadata_json=metadata,
    )
    db.add(row)
    db.flush()
    return row


def _team_read(team_id: int | None, name: str | None) -> LeaguePlayerHistoryTeam | None:
    return LeaguePlayerHistoryTeam(id=team_id, name=name) if team_id is not None or name else None


def current_player_status(db: Session, *, league_id: int, player_id: int) -> LeaguePlayerCurrentStatus:
    trade_processing = (
        db.query(TradeOfferItem.id)
        .join(TradeOffer, TradeOffer.id == TradeOfferItem.trade_offer_id)
        .filter(
            TradeOffer.league_id == league_id,
            TradeOfferItem.player_id == player_id,
            TradeOffer.status.in_(("accepted_pending", "commissioner_review")),
        )
        .first()
    )
    if trade_processing:
        return LeaguePlayerCurrentStatus(status="TRADE_PROCESSING")
    roster = (
        db.query(RosterEntry, Team)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(RosterEntry.league_id == league_id, RosterEntry.player_id == player_id)
        .one_or_none()
    )
    if roster:
        entry, team = roster
        owner = db.get(User, team.owner_user_id) if team.owner_user_id else None
        return LeaguePlayerCurrentStatus(
            status="ROSTERED" if entry.status != "ir" else "INACTIVE",
            fantasy_team_id=team.id,
            fantasy_team_name=team.name,
            manager_name=_manager_name(owner, team),
        )
    availability = (
        db.query(PlayerWaiverAvailability)
        .filter(PlayerWaiverAvailability.league_id == league_id, PlayerWaiverAvailability.player_id == player_id)
        .one_or_none()
    )
    state = (availability.state if availability else "free_agent").lower()
    if state in {"waivers", "waiver_locked"}:
        return LeaguePlayerCurrentStatus(status="ON_WAIVERS")
    if state == "claim_pending":
        return LeaguePlayerCurrentStatus(status="CLAIM_PENDING")
    return LeaguePlayerCurrentStatus(status="AVAILABLE")


def get_league_player_history(
    db: Session, *, league: League, player_id: int, limit: int, offset: int
) -> LeaguePlayerHistoryRead:
    player = db.get(Player, player_id)
    if player is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    query = db.query(LeaguePlayerEvent).filter(
        LeaguePlayerEvent.league_id == league.id, LeaguePlayerEvent.player_id == player_id
    )
    rows = query.order_by(LeaguePlayerEvent.occurred_at.desc(), LeaguePlayerEvent.id.desc()).all()
    events = [
        LeaguePlayerHistoryEvent(
            id=row.id,
            event_type=row.event_type,
            occurred_at=row.occurred_at,
            fantasy_team=_team_read(row.fantasy_team_id, row.fantasy_team_name_snapshot),
            from_team=_team_read(row.from_fantasy_team_id, row.from_team_name_snapshot),
            to_team=_team_read(row.to_fantasy_team_id, row.to_team_name_snapshot),
            manager=LeaguePlayerHistoryManager(id=row.manager_user_id, name=row.manager_name_snapshot)
            if row.manager_user_id is not None or row.manager_name_snapshot else None,
            draft_id=row.draft_id,
            draft_pick_id=row.draft_pick_id,
            trade_id=row.trade_id,
            waiver_claim_id=row.waiver_claim_id,
            transaction_id=row.transaction_id,
            player_value_at_event=row.player_value_snapshot,
            player_name=row.player_name_snapshot,
            position=row.position_snapshot,
            school=row.school_snapshot,
            metadata=row.event_metadata_json,
        )
        for row in rows
    ]
    recorded_draft_pick_ids = {event.draft_pick_id for event in events if event.draft_pick_id is not None}
    legacy_draft_rows = (
        db.query(DraftPick, Team)
        .join(Draft, Draft.id == DraftPick.draft_id)
        .join(Team, Team.id == DraftPick.team_id)
        .filter(Draft.league_id == league.id, DraftPick.player_id == player.id)
        .all()
    )
    for draft_pick, team in legacy_draft_rows:
        if draft_pick.id in recorded_draft_pick_ids:
            continue
        manager = db.get(User, draft_pick.made_by_user_id) if draft_pick.made_by_user_id else (
            db.get(User, team.owner_user_id) if team.owner_user_id else None
        )
        events.append(
            LeaguePlayerHistoryEvent(
                # Negative IDs are display-only compatibility rows. New draft
                # picks are captured by the append-only ledger at write time.
                id=-draft_pick.id,
                event_type=EVENT_AUTO_DRAFTED if draft_pick.auto_pick else EVENT_DRAFTED,
                occurred_at=_utc(draft_pick.created_at),
                fantasy_team=_team_read(team.id, team.name),
                to_team=_team_read(team.id, team.name),
                manager=LeaguePlayerHistoryManager(id=manager.id, name=_manager_name(manager, team)) if manager else None,
                draft_id=draft_pick.draft_id,
                draft_pick_id=draft_pick.id,
                player_value_at_event=player.sheet_projected_season_points,
                player_name=player.name,
                position=player.position,
                school=player.school,
                metadata={
                    "round": draft_pick.round_number,
                    "pick_in_round": draft_pick.round_pick,
                    "overall_pick": draft_pick.overall_pick,
                    "auto_pick": draft_pick.auto_pick,
                    "legacy_backfill": True,
                },
            )
        )
    events.sort(key=lambda event: (event.occurred_at, event.id), reverse=True)
    total = len(events)
    page = events[offset : offset + limit]
    return LeaguePlayerHistoryRead(
        league_id=league.id,
        player_id=player.id,
        current_status=current_player_status(db, league_id=league.id, player_id=player.id),
        events=page,
        total=total,
        limit=limit,
        offset=offset,
    )
