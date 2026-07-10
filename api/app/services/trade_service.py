from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.trade_review import TradeReview
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.trade import TradeCounterRequest, TradeOfferCreate, TradeOfferList, TradeOfferRead
from collegefootballfantasy_api.app.services.audit_service import record_audit_event
from collegefootballfantasy_api.app.services.notification_service import create_notification_event
from collegefootballfantasy_api.app.services.roster_legality import assign_best_roster_slot_for_team
from collegefootballfantasy_api.app.services.roster_lock_service import RosterLockError, ensure_player_unlocked

OPEN_TRADE_STATUSES = {"proposed", "commissioner_review"}
TERMINAL_TRADE_STATUSES = {"rejected", "cancelled", "expired", "vetoed", "processed", "failed", "countered"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_trade(db: Session, trade_id: int) -> TradeOffer:
    trade = (
        db.query(TradeOffer)
        .options(selectinload(TradeOffer.items), selectinload(TradeOffer.reviews))
        .filter(TradeOffer.id == trade_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    trade.items.sort(key=lambda item: item.id)
    trade.reviews.sort(key=lambda review: review.id)
    return trade


def _league_member_or_403(db: Session, league_id: int, user_id: int) -> LeagueMember:
    membership = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="league membership required")
    return membership


def _team_or_404(db: Session, league_id: int, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team not found")
    return team


def _user_can_manage_team(team: Team, current_user: User, league: League) -> bool:
    return team.owner_user_id == current_user.id or league.commissioner_user_id == current_user.id


def _require_team_manager(team: Team, current_user: User, league: League) -> None:
    if not _user_can_manage_team(team, current_user, league):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team ownership required")


def _is_commissioner(db: Session, league: League, current_user: User) -> bool:
    if league.commissioner_user_id == current_user.id:
        return True
    membership = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == current_user.id)
        .first()
    )
    return bool(membership and membership.role == "commissioner")


def _settings(db: Session, league_id: int) -> LeagueSettings:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return settings_row


def _players_from_payload(items) -> list[int]:
    player_ids = [item.player_id for item in items if item.player_id is not None]
    if not player_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade must include player items")
    if len(player_ids) != len(set(player_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="duplicate player in trade")
    return player_ids


def _validate_item_players_on_team(db: Session, *, league: League, team: Team, player_ids: list[int]) -> None:
    for player_id in player_ids:
        entry = (
            db.query(RosterEntry)
            .filter(
                RosterEntry.league_id == league.id,
                RosterEntry.team_id == team.id,
                RosterEntry.player_id == player_id,
            )
            .first()
        )
        if not entry:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade player is no longer on offering team")


def _record_trade_review(
    db: Session,
    *,
    trade: TradeOffer,
    current_user: User,
    action: str,
    reason: str | None = None,
) -> TradeReview:
    row = TradeReview(
        trade_offer_id=trade.id,
        reviewer_user_id=current_user.id,
        action=action,
        reason=reason,
    )
    db.add(row)
    return row


def _notify_user(db: Session, *, user_id: int | None, alert_type: str, title: str, body: str, payload: dict) -> None:
    if user_id is None:
        return
    trade_id = payload.get("trade_id")
    create_notification_event(
        db,
        user_id=user_id,
        league_id=payload.get("league_id") if isinstance(payload.get("league_id"), int) else None,
        alert_type=alert_type,
        title=title,
        body=body,
        payload=payload,
        dedupe_key=f"trade:{trade_id}:{alert_type}:{user_id}" if isinstance(trade_id, int) else None,
        source_entity_type="trade_offer" if isinstance(trade_id, int) else None,
        source_entity_id=trade_id if isinstance(trade_id, int) else None,
        deep_link=f"/trade/{payload.get('league_id')}" if isinstance(payload.get("league_id"), int) and isinstance(trade_id, int) else None,
    )


def _notify_trade_participants(db: Session, *, trade: TradeOffer, title: str, body: str, alert_type: str) -> None:
    proposing_team = db.get(Team, trade.proposing_team_id)
    receiving_team = db.get(Team, trade.receiving_team_id)
    payload = {"trade_id": trade.id, "league_id": trade.league_id, "status": trade.status}
    _notify_user(db, user_id=proposing_team.owner_user_id if proposing_team else None, alert_type=alert_type, title=title, body=body, payload=payload)
    _notify_user(db, user_id=receiving_team.owner_user_id if receiving_team else None, alert_type=alert_type, title=title, body=body, payload=payload)


def _serialize_trade(trade: TradeOffer) -> TradeOfferRead:
    return TradeOfferRead.model_validate(trade)


def create_trade_offer(db: Session, *, league: League, payload: TradeOfferCreate, current_user: User) -> TradeOfferRead:
    _league_member_or_403(db, league.id, current_user.id)
    proposing_team = _team_or_404(db, league.id, payload.proposing_team_id)
    receiving_team = _team_or_404(db, league.id, payload.receiving_team_id)
    if proposing_team.id == receiving_team.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot trade with the same team")
    _require_team_manager(proposing_team, current_user, league)
    proposing_player_ids = _players_from_payload(payload.proposing_items)
    receiving_player_ids = _players_from_payload(payload.receiving_items)
    if set(proposing_player_ids) & set(receiving_player_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="player cannot appear on both sides")
    _validate_item_players_on_team(db, league=league, team=proposing_team, player_ids=proposing_player_ids)
    _validate_item_players_on_team(db, league=league, team=receiving_team, player_ids=receiving_player_ids)

    trade = TradeOffer(
        league_id=league.id,
        proposing_team_id=proposing_team.id,
        receiving_team_id=receiving_team.id,
        status="proposed",
        expires_at=payload.expires_at,
        message=payload.message,
        created_by=current_user.id,
    )
    db.add(trade)
    db.flush()
    for item in payload.proposing_items:
        db.add(TradeOfferItem(trade_offer_id=trade.id, team_id=proposing_team.id, player_id=item.player_id, draft_pick_id=item.draft_pick_id))
    for item in payload.receiving_items:
        db.add(TradeOfferItem(trade_offer_id=trade.id, team_id=receiving_team.id, player_id=item.player_id, draft_pick_id=item.draft_pick_id))
    _record_trade_review(db, trade=trade, current_user=current_user, action="proposed")
    _notify_trade_participants(
        db,
        trade=trade,
        title="Trade Proposed",
        body="A trade offer has been proposed.",
        alert_type="TRADE_PROPOSED",
    )
    record_audit_event(
        db,
        action="trade.proposed",
        entity_type="trade_offer",
        entity_id=trade.id,
        league_id=league.id,
        team_id=proposing_team.id,
        actor_user_id=current_user.id,
        after={"receiving_team_id": receiving_team.id, "proposing_player_ids": proposing_player_ids, "receiving_player_ids": receiving_player_ids},
    )
    db.commit()
    return get_trade_offer(db, trade.id, current_user)


def list_trade_offers(db: Session, *, league: League, current_user: User) -> TradeOfferList:
    _league_member_or_403(db, league.id, current_user.id)
    rows = (
        db.query(TradeOffer)
        .options(selectinload(TradeOffer.items), selectinload(TradeOffer.reviews))
        .filter(TradeOffer.league_id == league.id)
        .order_by(TradeOffer.created_at.desc(), TradeOffer.id.desc())
        .all()
    )
    return TradeOfferList(data=[_serialize_trade(row) for row in rows], total=len(rows))


def get_trade_offer(db: Session, trade_id: int, current_user: User) -> TradeOfferRead:
    trade = _load_trade(db, trade_id)
    _league_member_or_403(db, trade.league_id, current_user.id)
    return _serialize_trade(trade)


def _expire_if_needed(db: Session, trade: TradeOffer) -> None:
    expires_at = trade.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if trade.status in OPEN_TRADE_STATUSES and expires_at is not None and expires_at <= _utc_now():
        trade.status = "expired"
        db.add(trade)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer expired")


def _require_open_trade(db: Session, trade: TradeOffer) -> None:
    _expire_if_needed(db, trade)
    if trade.status not in OPEN_TRADE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade offer is {trade.status}")


def _trade_player_ids(trade: TradeOffer, team_id: int) -> list[int]:
    return [item.player_id for item in trade.items if item.team_id == team_id and item.player_id is not None]


def _validate_trade_players_still_owned(db: Session, *, league: League, trade: TradeOffer) -> None:
    for team_id in (trade.proposing_team_id, trade.receiving_team_id):
        for player_id in _trade_player_ids(trade, team_id):
            exists = (
                db.query(RosterEntry.id)
                .filter(
                    RosterEntry.league_id == league.id,
                    RosterEntry.team_id == team_id,
                    RosterEntry.player_id == player_id,
                )
                .first()
            )
            if not exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade player is no longer on offering team")


def _lock_trade_rosters(db: Session, league_id: int, *team_ids: int) -> list[RosterEntry]:
    return (
        db.query(RosterEntry)
        .filter(RosterEntry.league_id == league_id, RosterEntry.team_id.in_(team_ids))
        .with_for_update()
        .all()
    )


def _entry_by_team_player(entries: list[RosterEntry]) -> dict[tuple[int, int], RosterEntry]:
    return {(entry.team_id, entry.player_id): entry for entry in entries}


def _validate_trade_locks(db: Session, *, league: League, player_ids: list[int]) -> None:
    for player_id in player_ids:
        player = db.get(Player, player_id)
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade player not found")
        try:
            ensure_player_unlocked(db, league, player)
        except RosterLockError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _process_trade_roster_swap(db: Session, *, league: League, trade: TradeOffer) -> None:
    proposing_ids = _trade_player_ids(trade, trade.proposing_team_id)
    receiving_ids = _trade_player_ids(trade, trade.receiving_team_id)
    all_player_ids = proposing_ids + receiving_ids
    if not proposing_ids or not receiving_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade must include players on both sides")
    _validate_trade_locks(db, league=league, player_ids=all_player_ids)
    settings_row = _settings(db, league.id)
    roster_slots = settings_row.roster_slots_json
    superflex_enabled = bool(settings_row.superflex_enabled)
    entries = _lock_trade_rosters(db, league.id, trade.proposing_team_id, trade.receiving_team_id)
    by_team_player = _entry_by_team_player(entries)

    outgoing_entries: list[RosterEntry] = []
    for player_id in proposing_ids:
        entry = by_team_player.get((trade.proposing_team_id, player_id))
        if not entry:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade player is no longer on offering team")
        outgoing_entries.append(entry)
    for player_id in receiving_ids:
        entry = by_team_player.get((trade.receiving_team_id, player_id))
        if not entry:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade player is no longer on offering team")
        outgoing_entries.append(entry)

    for entry in outgoing_entries:
        db.delete(entry)
    db.flush()

    for player_id in proposing_ids:
        player = db.get(Player, player_id)
        slot = assign_best_roster_slot_for_team(db, trade.receiving_team_id, player.position, roster_slots, superflex_enabled=superflex_enabled)
        if not slot:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="receiving roster would be illegal")
        db.add(RosterEntry(league_id=league.id, team_id=trade.receiving_team_id, player_id=player_id, slot=slot, status="active"))
    for player_id in receiving_ids:
        player = db.get(Player, player_id)
        slot = assign_best_roster_slot_for_team(db, trade.proposing_team_id, player.position, roster_slots, superflex_enabled=superflex_enabled)
        if not slot:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="proposing roster would be illegal")
        db.add(RosterEntry(league_id=league.id, team_id=trade.proposing_team_id, player_id=player_id, slot=slot, status="active"))

    for player_id in proposing_ids:
        db.add(Transaction(league_id=league.id, team_id=trade.receiving_team_id, transaction_type="trade", player_id=player_id, reason=f"Trade {trade.id} processed"))
    for player_id in receiving_ids:
        db.add(Transaction(league_id=league.id, team_id=trade.proposing_team_id, transaction_type="trade", player_id=player_id, reason=f"Trade {trade.id} processed"))


def accept_trade_offer(db: Session, *, trade_id: int, current_user: User) -> TradeOfferRead:
    trade = _load_trade(db, trade_id)
    league = db.get(League, trade.league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    receiving_team = db.get(Team, trade.receiving_team_id)
    if not receiving_team or receiving_team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="receiving team owner required")
    _require_open_trade(db, trade)
    settings_row = _settings(db, league.id)
    if settings_row.trade_review_type == "commissioner":
        _validate_trade_players_still_owned(db, league=league, trade=trade)
        trade.status = "commissioner_review"
        _notify_trade_participants(db, trade=trade, title="Trade Accepted", body="A trade is pending commissioner review.", alert_type="TRADE_ACCEPTED")
    else:
        _process_trade_roster_swap(db, league=league, trade=trade)
        trade.status = "processed"
        _notify_trade_participants(db, trade=trade, title="Trade Processed", body="A trade has been processed.", alert_type="TRADE_PROCESSED")
    _record_trade_review(db, trade=trade, current_user=current_user, action="accepted")
    record_audit_event(db, action="trade.accepted", entity_type="trade_offer", entity_id=trade.id, league_id=trade.league_id, actor_user_id=current_user.id, after={"status": trade.status})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        trade.status = "failed"
        db.add(trade)
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade processing failed") from exc
    return get_trade_offer(db, trade.id, current_user)


def reject_trade_offer(db: Session, *, trade_id: int, current_user: User, reason: str | None = None) -> TradeOfferRead:
    trade = _load_trade(db, trade_id)
    receiving_team = db.get(Team, trade.receiving_team_id)
    if not receiving_team or receiving_team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="receiving team owner required")
    _require_open_trade(db, trade)
    trade.status = "rejected"
    _record_trade_review(db, trade=trade, current_user=current_user, action="rejected", reason=reason)
    _notify_trade_participants(db, trade=trade, title="Trade Rejected", body="A trade offer was rejected.", alert_type="TRADE_REJECTED")
    record_audit_event(db, action="trade.rejected", entity_type="trade_offer", entity_id=trade.id, league_id=trade.league_id, actor_user_id=current_user.id, after={"status": trade.status, "reason": reason})
    db.commit()
    return get_trade_offer(db, trade.id, current_user)


def cancel_trade_offer(db: Session, *, trade_id: int, current_user: User, reason: str | None = None) -> TradeOfferRead:
    trade = _load_trade(db, trade_id)
    proposing_team = db.get(Team, trade.proposing_team_id)
    if not proposing_team or proposing_team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="proposing team owner required")
    _require_open_trade(db, trade)
    trade.status = "cancelled"
    _record_trade_review(db, trade=trade, current_user=current_user, action="cancelled", reason=reason)
    _notify_trade_participants(db, trade=trade, title="Trade Cancelled", body="A trade offer was cancelled.", alert_type="TRADE_CANCELLED")
    record_audit_event(db, action="trade.cancelled", entity_type="trade_offer", entity_id=trade.id, league_id=trade.league_id, actor_user_id=current_user.id, after={"status": trade.status, "reason": reason})
    db.commit()
    return get_trade_offer(db, trade.id, current_user)


def counter_trade_offer(db: Session, *, trade_id: int, payload: TradeCounterRequest, current_user: User) -> TradeOfferRead:
    original = _load_trade(db, trade_id)
    league = db.get(League, original.league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    _require_open_trade(db, original)
    receiving_team = db.get(Team, original.receiving_team_id)
    if not receiving_team or receiving_team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="receiving team owner required")
    original.status = "countered"
    _record_trade_review(db, trade=original, current_user=current_user, action="countered", reason=payload.reason)
    db.flush()
    new_payload = TradeOfferCreate(
        proposing_team_id=payload.proposing_team_id,
        receiving_team_id=payload.receiving_team_id,
        proposing_items=payload.proposing_items,
        receiving_items=payload.receiving_items,
        message=payload.message,
        expires_at=payload.expires_at,
    )
    created = create_trade_offer(db, league=league, payload=new_payload, current_user=current_user)
    return created


def commissioner_veto_trade(db: Session, *, trade_id: int, current_user: User, reason: str | None = None) -> TradeOfferRead:
    trade = _load_trade(db, trade_id)
    league = db.get(League, trade.league_id)
    if not league or not _is_commissioner(db, league, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner only")
    if trade.status not in {"proposed", "accepted", "commissioner_review"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade offer is {trade.status}")
    trade.status = "vetoed"
    _record_trade_review(db, trade=trade, current_user=current_user, action="vetoed", reason=reason)
    _notify_trade_participants(db, trade=trade, title="Trade Vetoed", body="A trade was vetoed by the commissioner.", alert_type="TRADE_VETOED")
    record_audit_event(db, action="trade.vetoed", entity_type="trade_offer", entity_id=trade.id, league_id=trade.league_id, actor_user_id=current_user.id, after={"status": trade.status, "reason": reason})
    db.commit()
    return get_trade_offer(db, trade.id, current_user)


def commissioner_approve_trade(db: Session, *, trade_id: int, current_user: User, reason: str | None = None) -> TradeOfferRead:
    trade = _load_trade(db, trade_id)
    league = db.get(League, trade.league_id)
    if not league or not _is_commissioner(db, league, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner only")
    if trade.status != "commissioner_review":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade offer is {trade.status}")
    _process_trade_roster_swap(db, league=league, trade=trade)
    trade.status = "processed"
    _record_trade_review(db, trade=trade, current_user=current_user, action="approved", reason=reason)
    _notify_trade_participants(db, trade=trade, title="Trade Processed", body="A trade was approved and processed.", alert_type="TRADE_PROCESSED")
    record_audit_event(db, action="trade.approved", entity_type="trade_offer", entity_id=trade.id, league_id=trade.league_id, actor_user_id=current_user.id, after={"status": trade.status, "reason": reason})
    db.commit()
    return get_trade_offer(db, trade.id, current_user)
