from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.trade_review import TradeReview
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.trade import (
    TradeActionRequest,
    TradeOfferCreate,
    TradeOfferItemRead,
    TradeOfferList,
    TradeOfferRead,
    TradeReviewRead,
)
from collegefootballfantasy_api.app.services.chat_service import (
    create_trade_finalized_chat_message,
    mark_trade_finalized_chat_message_processed,
)
from collegefootballfantasy_api.app.services.league_weeks import (
    current_cfb_week_state,
    is_cfb_game_week_active,
    next_cfb_trade_process_time,
)
from collegefootballfantasy_api.app.services.notification_service import legacy_user_key
from collegefootballfantasy_api.app.services.player_lock_service import locked_player_ids

TRADE_STATUS_PROPOSED = "proposed"
TRADE_STATUS_ACCEPTED_PENDING = "accepted_pending"
TRADE_STATUS_COMMISSIONER_REVIEW = "commissioner_review"
TRADE_STATUS_PROCESSED = "processed"
TRADE_STATUS_REJECTED = "rejected"
TRADE_STATUS_CANCELLED = "cancelled"
TRADE_STATUS_COUNTERED = "countered"
TRADE_STATUS_VETOED = "vetoed"
TRADE_STATUS_FAILED = "failed"

OPEN_STATUSES = {TRADE_STATUS_PROPOSED, TRADE_STATUS_COMMISSIONER_REVIEW}
FINAL_STATUSES = {
    TRADE_STATUS_PROCESSED,
    TRADE_STATUS_REJECTED,
    TRADE_STATUS_CANCELLED,
    TRADE_STATUS_COUNTERED,
    TRADE_STATUS_VETOED,
    TRADE_STATUS_FAILED,
}
STARTER_SLOTS = {"QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K"}
DEFAULT_TRADE_EXPIRATION_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _trade_timezone(db: Session, league_id: int) -> str:
    draft = db.query(Draft).filter(Draft.league_id == league_id).first()
    return draft.timezone if draft and draft.timezone else "UTC"


def _league_settings(db: Session, league_id: int) -> LeagueSettings | None:
    return db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()


def _trade_requires_commissioner(db: Session, league_id: int) -> bool:
    settings = _league_settings(db, league_id)
    review_type = (settings.trade_review_type or "none").strip().lower() if settings else "none"
    if review_type not in {"none", "commissioner"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unsupported trade review type")
    return review_type == "commissioner"


def _ensure_trade_deadline_open(db: Session, league: League, now: datetime) -> None:
    settings = _league_settings(db, league.id)
    if not settings:
        return
    if settings.trade_deadline_at is not None and _as_utc(settings.trade_deadline_at) <= _as_utc(now):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade deadline has passed")
    if settings.trade_deadline_week is not None:
        week_state = current_cfb_week_state(league.season_year, _as_utc(now), _trade_timezone(db, league.id))
        if week_state.week >= settings.trade_deadline_week:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade deadline has passed")


def _member_or_404(db: Session, league_id: int, user_id: int) -> LeagueMember:
    member = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a league member")
    return member


def _team_or_404(db: Session, league_id: int, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team not found in league")
    return team


def _require_team_owner(team: Team, user: User) -> None:
    if team.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the team owner can perform this action")


def _require_commissioner(league: League, user: User) -> None:
    if league.commissioner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the commissioner can review this trade")


def _load_offer(db: Session, trade_id: int, *, for_update: bool = False) -> TradeOffer:
    query = (
        db.query(TradeOffer)
        .options(joinedload(TradeOffer.items).joinedload(TradeOfferItem.player), joinedload(TradeOffer.reviews))
        .filter(TradeOffer.id == trade_id)
    )
    if for_update:
        query = query.with_for_update(of=TradeOffer)
    offer = query.first()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    return offer


def _offer_participants(db: Session, offer: TradeOffer) -> tuple[Team, Team]:
    proposing = _team_or_404(db, offer.league_id, offer.proposing_team_id)
    receiving = _team_or_404(db, offer.league_id, offer.receiving_team_id)
    return proposing, receiving


def _add_review(db: Session, offer: TradeOffer, action: str, user_id: int | None, reason: str | None = None) -> None:
    db.add(TradeReview(trade_offer_id=offer.id, reviewer_user_id=user_id, action=action, reason=reason))


def _create_alert(
    db: Session,
    *,
    user_id: int | None,
    alert_type: str,
    title: str,
    body: str,
    league_id: int,
    trade_id: int,
) -> None:
    if user_id is None:
        return
    db.add(
        NotificationLog(
            user_id=user_id,
            user_key=legacy_user_key(user_id),
            alert_type=alert_type,
            title=title,
            body=body,
            payload={"league_id": league_id, "trade_id": trade_id, "deep_link": f"/leagues/{league_id}/trades/{trade_id}"},
            sent_at=datetime.utcnow(),
        )
    )


def _notify_participants(db: Session, offer: TradeOffer, alert_type: str, title: str, body: str) -> None:
    proposing, receiving = _offer_participants(db, offer)
    for user_id in {proposing.owner_user_id, receiving.owner_user_id}:
        _create_alert(
            db,
            user_id=user_id,
            alert_type=alert_type,
            title=title,
            body=body,
            league_id=offer.league_id,
            trade_id=offer.id,
        )


def _announce_trade_finalized(
    db: Session,
    offer: TradeOffer,
    *,
    finalized_at: datetime,
) -> None:
    """Write the binding event in the transaction that finalizes the offer."""
    create_trade_finalized_chat_message(
        db,
        offer,
        finalized_at=finalized_at,
        process_after=offer.process_after,
    )


def _player_ids_for_offer(offer: TradeOffer) -> list[int]:
    return [item.player_id for item in offer.items if item.player_id is not None]


def _ensure_not_expired(offer: TradeOffer, now: datetime | None = None) -> None:
    if offer.expires_at is not None and _as_utc(offer.expires_at) <= _as_utc(now or _utcnow()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer has expired")


def _player_ids_from_payload(payload: TradeOfferCreate) -> list[int]:
    ids: list[int] = []
    for item in [*payload.give_items, *payload.receive_items]:
        if item.player_id is not None:
            ids.append(item.player_id)
        if item.draft_pick_id is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft pick trading is not enabled yet")
    return ids


def _validate_player_ownership(db: Session, league_id: int, team_id: int, player_ids: list[int]) -> None:
    if not player_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade requires rostered players")
    found = {
        row.player_id
        for row in db.query(RosterEntry)
        .filter(RosterEntry.league_id == league_id, RosterEntry.team_id == team_id)
        .filter(RosterEntry.player_id.in_(player_ids))
        .all()
    }
    missing = set(player_ids) - found
    if missing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="one or more players are no longer owned by that team")


def _validate_payload(db: Session, league_id: int, payload: TradeOfferCreate) -> tuple[Team, Team]:
    proposing = _team_or_404(db, league_id, payload.proposing_team_id)
    receiving = _team_or_404(db, league_id, payload.receiving_team_id)
    if proposing.id == receiving.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot trade with the same team")

    give_player_ids = [item.player_id for item in payload.give_items if item.player_id is not None]
    receive_player_ids = [item.player_id for item in payload.receive_items if item.player_id is not None]
    for item in payload.give_items:
        if item.team_id != proposing.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="give items must belong to proposing team")
    for item in payload.receive_items:
        if item.team_id != receiving.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="receive items must belong to receiving team")
    _player_ids_from_payload(payload)
    _validate_player_ownership(db, league_id, proposing.id, give_player_ids)
    _validate_player_ownership(db, league_id, receiving.id, receive_player_ids)
    return proposing, receiving


def _validate_offer_ownership(db: Session, offer: TradeOffer) -> None:
    proposing_ids = [item.player_id for item in offer.items if item.team_id == offer.proposing_team_id and item.player_id]
    receiving_ids = [item.player_id for item in offer.items if item.team_id == offer.receiving_team_id and item.player_id]
    _validate_player_ownership(db, offer.league_id, offer.proposing_team_id, proposing_ids)
    _validate_player_ownership(db, offer.league_id, offer.receiving_team_id, receiving_ids)


def _validate_no_locked_players(db: Session, league: League, offer: TradeOffer, now: datetime | None = None) -> None:
    player_ids = _player_ids_for_offer(offer)
    if not player_ids:
        return
    week_state = current_cfb_week_state(league.season_year, now or _utcnow(), _trade_timezone(db, league.id))
    locked = locked_player_ids(
        db,
        player_ids=player_ids,
        season=league.season_year,
        week=week_state.week,
        now=now or _utcnow(),
    )
    if locked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="locked player cannot be traded")


def _slot_limits(db: Session, league_id: int) -> dict[str, int]:
    settings = _league_settings(db, league_id)
    raw = settings.roster_slots_json if settings and settings.roster_slots_json else {}
    return {
        "QB": int(raw.get("QB", 1)),
        "RB": int(raw.get("RB", 2)),
        "WR": int(raw.get("WR", 2)),
        "TE": int(raw.get("TE", 1)),
        "FLEX": int(raw.get("FLEX", 1)),
        "SUPERFLEX": int(raw.get("SUPERFLEX", 0)),
        "K": int(raw.get("K", 1)),
        "BENCH": int(raw.get("BENCH", raw.get("BE", 5))),
        "IR": int(raw.get("IR", 1)),
    }


def _eligible_slots(position: str) -> list[str]:
    pos = position.upper()
    slots = [pos]
    if pos in {"RB", "WR", "TE"}:
        slots.append("FLEX")
    if pos in {"QB", "RB", "WR", "TE"}:
        slots.append("SUPERFLEX")
    slots.append("BENCH")
    return slots


def _assign_slot(player: Player, counts: dict[str, int], limits: dict[str, int]) -> str:
    for slot in _eligible_slots(player.position):
        if counts.get(slot, 0) < limits.get(slot, 0):
            counts[slot] = counts.get(slot, 0) + 1
            return slot
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade would create an illegal roster")


def _process_roster_swap(db: Session, offer: TradeOffer, actor_user_id: int | None = None) -> None:
    limits = _slot_limits(db, offer.league_id)
    player_ids = _player_ids_for_offer(offer)
    outgoing_entries = (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.league_id == offer.league_id, RosterEntry.player_id.in_(player_ids))
        .with_for_update(of=RosterEntry)
        .all()
    )
    entry_by_player = {entry.player_id: entry for entry in outgoing_entries}
    if len(entry_by_player) != len(set(player_ids)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="one or more traded players are no longer rostered")

    target_by_player: dict[int, int] = {}
    for item in offer.items:
        if item.player_id is None:
            continue
        if item.team_id == offer.proposing_team_id:
            target_by_player[item.player_id] = offer.receiving_team_id
        elif item.team_id == offer.receiving_team_id:
            target_by_player[item.player_id] = offer.proposing_team_id
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade item team no longer matches offer")

    remaining_counts_by_team: dict[int, dict[str, int]] = {}
    for team_id in {offer.proposing_team_id, offer.receiving_team_id}:
        remaining_entries = (
            db.query(RosterEntry)
            .filter(RosterEntry.league_id == offer.league_id, RosterEntry.team_id == team_id)
            .filter(~RosterEntry.player_id.in_(player_ids))
            .with_for_update(of=RosterEntry)
            .all()
        )
        counts: dict[str, int] = {}
        for entry in remaining_entries:
            counts[entry.slot] = counts.get(entry.slot, 0) + 1
        remaining_counts_by_team[team_id] = counts

    moved_players: list[tuple[int, int, int]] = []
    for entry in outgoing_entries:
        source_team_id = entry.team_id
        target_team_id = target_by_player[entry.player_id]
        db.delete(entry)
        moved_players.append((entry.player_id, source_team_id, target_team_id))
    db.flush()

    players = db.query(Player).filter(Player.id.in_(player_ids)).all()
    player_by_id = {player.id: player for player in players}
    for player_id, _source_team_id, target_team_id in moved_players:
        player = player_by_id[player_id]
        slot = _assign_slot(player, remaining_counts_by_team[target_team_id], limits)
        db.add(
            RosterEntry(
                league_id=offer.league_id,
                team_id=target_team_id,
                player_id=player_id,
                slot=slot,
                status="active",
            )
        )
        db.add(
            Transaction(
                league_id=offer.league_id,
                team_id=target_team_id,
                transaction_type="trade_processed",
                player_id=player_id,
                created_by_user_id=actor_user_id,
                reason=f"Trade offer #{offer.id} processed",
            )
        )


def _serialize_offer(offer: TradeOffer) -> TradeOfferRead:
    items = [
        TradeOfferItemRead(
            id=item.id,
            trade_offer_id=item.trade_offer_id,
            team_id=item.team_id,
            player_id=item.player_id,
            draft_pick_id=item.draft_pick_id,
            item_type=item.item_type,
            player_name=item.player.name if item.player else None,
            player_position=item.player.position if item.player else None,
            player_school=item.player.school if item.player else None,
        )
        for item in sorted(offer.items, key=lambda row: row.id)
    ]
    reviews = [
        TradeReviewRead(
            id=review.id,
            trade_offer_id=review.trade_offer_id,
            reviewer_user_id=review.reviewer_user_id,
            action=review.action,
            reason=review.reason,
            created_at=review.created_at,
        )
        for review in sorted(offer.reviews, key=lambda row: row.id)
    ]
    return TradeOfferRead(
        id=offer.id,
        league_id=offer.league_id,
        proposing_team_id=offer.proposing_team_id,
        receiving_team_id=offer.receiving_team_id,
        created_by_user_id=offer.created_by_user_id,
        status=offer.status,
        message=offer.message,
        accepted_at=offer.accepted_at,
        process_after=offer.process_after,
        processed_at=offer.processed_at,
        expires_at=offer.expires_at,
        failure_reason=offer.failure_reason,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
        items=items,
        reviews=reviews,
    )


def list_trade_offers(db: Session, league: League, current_user: User) -> TradeOfferList:
    _member_or_404(db, league.id, current_user.id)
    rows = (
        db.query(TradeOffer)
        .options(joinedload(TradeOffer.items).joinedload(TradeOfferItem.player), joinedload(TradeOffer.reviews))
        .filter(TradeOffer.league_id == league.id)
        .order_by(TradeOffer.created_at.desc(), TradeOffer.id.desc())
        .all()
    )
    return TradeOfferList(data=[_serialize_offer(row) for row in rows], total=len(rows))


def get_trade_offer(db: Session, league: League, trade_id: int, current_user: User) -> TradeOfferRead:
    _member_or_404(db, league.id, current_user.id)
    offer = _load_offer(db, trade_id)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    return _serialize_offer(offer)


def create_trade_offer(db: Session, league: League, current_user: User, payload: TradeOfferCreate) -> TradeOfferRead:
    _member_or_404(db, league.id, current_user.id)
    _ensure_trade_deadline_open(db, league, _utcnow())
    proposing, receiving = _validate_payload(db, league.id, payload)
    _require_team_owner(proposing, current_user)

    offer = TradeOffer(
        league_id=league.id,
        proposing_team_id=proposing.id,
        receiving_team_id=receiving.id,
        created_by_user_id=current_user.id,
        status=TRADE_STATUS_PROPOSED,
        message=payload.message,
        expires_at=_utcnow() + timedelta(days=DEFAULT_TRADE_EXPIRATION_DAYS),
    )
    db.add(offer)
    db.flush()
    for item in [*payload.give_items, *payload.receive_items]:
        db.add(
            TradeOfferItem(
                trade_offer_id=offer.id,
                team_id=item.team_id,
                player_id=item.player_id,
                draft_pick_id=item.draft_pick_id,
                item_type="player" if item.player_id is not None else "draft_pick",
            )
        )
    _add_review(db, offer, "proposed", current_user.id, payload.message)
    _create_alert(
        db,
        user_id=receiving.owner_user_id,
        alert_type="TRADE_PROPOSED",
        title="Trade Offer Received",
        body=f"{proposing.name} sent you a trade offer.",
        league_id=league.id,
        trade_id=offer.id,
    )
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def _complete_accepted_trade(
    db: Session,
    *,
    league: League,
    offer: TradeOffer,
    actor_user_id: int | None,
    now: datetime,
    review_action: str,
    review_reason: str | None = None,
) -> None:
    _validate_offer_ownership(db, offer)
    _validate_no_locked_players(db, league, offer, now)
    _process_roster_swap(db, offer, actor_user_id=actor_user_id)
    offer.status = TRADE_STATUS_PROCESSED
    offer.accepted_at = offer.accepted_at or now
    offer.process_after = now
    offer.processed_at = now
    offer.failure_reason = None
    _add_review(db, offer, review_action, actor_user_id, review_reason)
    _notify_participants(db, offer, "TRADE_PROCESSED", "Trade Processed", "Accepted trade players have moved rosters.")


def accept_trade_offer(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status != TRADE_STATUS_PROPOSED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer is not pending acceptance")
    now = _utcnow()
    _ensure_trade_deadline_open(db, league, now)
    _ensure_not_expired(offer, now)
    _proposing, receiving = _offer_participants(db, offer)
    _require_team_owner(receiving, current_user)
    _validate_offer_ownership(db, offer)
    _validate_no_locked_players(db, league, offer, now)

    if _trade_requires_commissioner(db, league.id):
        offer.status = TRADE_STATUS_COMMISSIONER_REVIEW
        offer.accepted_at = now
        body = "Trade accepted and sent to commissioner review."
    elif is_cfb_game_week_active(now, _trade_timezone(db, league.id)):
        offer.status = TRADE_STATUS_ACCEPTED_PENDING
        offer.accepted_at = now
        offer.process_after = next_cfb_trade_process_time(now, _trade_timezone(db, league.id))
        body = f"Trade accepted. It will process after {offer.process_after.isoformat()}."
    else:
        _complete_accepted_trade(
            db,
            league=league,
            offer=offer,
            actor_user_id=current_user.id,
            now=now,
            review_action="processed",
        )
        body = "Trade accepted and processed."
    _add_review(db, offer, "accepted", current_user.id, payload.reason)
    _notify_participants(db, offer, "TRADE_ACCEPTED", "Trade Accepted", body)
    if offer.status != TRADE_STATUS_COMMISSIONER_REVIEW:
        _announce_trade_finalized(db, offer, finalized_at=now)
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def commissioner_approve_trade(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    _require_commissioner(league, current_user)
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status != TRADE_STATUS_COMMISSIONER_REVIEW:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer is not awaiting commissioner review")
    _validate_offer_ownership(db, offer)
    now = _utcnow()
    _ensure_trade_deadline_open(db, league, now)
    _validate_no_locked_players(db, league, offer, now)
    if is_cfb_game_week_active(now, _trade_timezone(db, league.id)):
        offer.status = TRADE_STATUS_ACCEPTED_PENDING
        offer.accepted_at = offer.accepted_at or now
        offer.process_after = next_cfb_trade_process_time(now, _trade_timezone(db, league.id))
        body = f"Trade approved. It will process after {offer.process_after.isoformat()}."
    else:
        _complete_accepted_trade(
            db,
            league=league,
            offer=offer,
            actor_user_id=current_user.id,
            now=now,
            review_action="processed",
        )
        body = "Trade approved and processed."
    _add_review(db, offer, "approved", current_user.id, payload.reason)
    _notify_participants(db, offer, "TRADE_APPROVED", "Trade Approved", body)
    _announce_trade_finalized(db, offer, finalized_at=now)
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def reject_trade_offer(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status != TRADE_STATUS_PROPOSED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer is not pending rejection")
    _proposing, receiving = _offer_participants(db, offer)
    _require_team_owner(receiving, current_user)
    offer.status = TRADE_STATUS_REJECTED
    _add_review(db, offer, "rejected", current_user.id, payload.reason)
    _notify_participants(db, offer, "TRADE_REJECTED", "Trade Rejected", "A trade offer was rejected.")
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def cancel_trade_offer(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status not in OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer can no longer be cancelled")
    proposing, _receiving = _offer_participants(db, offer)
    _require_team_owner(proposing, current_user)
    offer.status = TRADE_STATUS_CANCELLED
    _add_review(db, offer, "cancelled", current_user.id, payload.reason)
    _notify_participants(db, offer, "TRADE_CANCELLED", "Trade Cancelled", "A trade offer was cancelled.")
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def counter_trade_offer(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="counter offers are unavailable until linked replacement offers are implemented",
    )


def commissioner_veto_trade(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    _require_commissioner(league, current_user)
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status not in {TRADE_STATUS_COMMISSIONER_REVIEW, TRADE_STATUS_ACCEPTED_PENDING}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer is not reviewable")
    offer.status = TRADE_STATUS_VETOED
    _add_review(db, offer, "vetoed", current_user.id, payload.reason)
    _notify_participants(db, offer, "TRADE_VETOED", "Trade Vetoed", "A trade offer was vetoed.")
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def process_trade_offers_once(db: Session, now: datetime | None = None) -> dict[str, int]:
    current = _as_utc(now or _utcnow())
    offer_ids = [
        offer_id
        for (offer_id,) in (
        db.query(TradeOffer)
        .with_entities(TradeOffer.id)
        .filter(TradeOffer.status == TRADE_STATUS_ACCEPTED_PENDING)
        .filter(TradeOffer.process_after.isnot(None), TradeOffer.process_after <= current)
        .order_by(TradeOffer.process_after.asc(), TradeOffer.id.asc())
        .all()
        )
    ]
    processed = 0
    failed = 0
    for offer_id in offer_ids:
        offer = (
            db.query(TradeOffer)
            .options(joinedload(TradeOffer.items).joinedload(TradeOfferItem.player), joinedload(TradeOffer.reviews))
            .filter(TradeOffer.id == offer_id)
            .with_for_update(skip_locked=True, of=TradeOffer)
            .first()
        )
        if (
            offer is None
            or offer.status != TRADE_STATUS_ACCEPTED_PENDING
            or offer.process_after is None
            or _as_utc(offer.process_after) > current
        ):
            continue
        league = db.get(League, offer.league_id)
        if not league:
            offer.status = TRADE_STATUS_FAILED
            offer.failure_reason = "league no longer exists"
            failed += 1
            db.commit()
            continue
        timezone_name = _trade_timezone(db, league.id)
        if is_cfb_game_week_active(current, timezone_name):
            continue
        try:
            with db.begin_nested():
                _ensure_trade_deadline_open(db, league, current)
                _validate_offer_ownership(db, offer)
                _validate_no_locked_players(db, league, offer, current)
                _complete_accepted_trade(
                    db,
                    league=league,
                    offer=offer,
                    actor_user_id=None,
                    now=current,
                    review_action="processed",
                )
                mark_trade_finalized_chat_message_processed(db, offer)
            processed += 1
        except Exception as exc:
            offer.status = TRADE_STATUS_FAILED
            offer.failure_reason = str(exc.detail) if isinstance(exc, HTTPException) else "trade processing failed"
            _add_review(db, offer, "failed", None, offer.failure_reason)
            _notify_participants(db, offer, "TRADE_FAILED", "Trade Failed", offer.failure_reason)
            failed += 1
        db.commit()
    return {"processed": processed, "failed": failed}
