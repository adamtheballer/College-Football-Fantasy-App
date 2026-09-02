from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.trade_review import TradeReview
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.trade import (
    TradeActionRequest,
    TradeOfferCounterCreate,
    TradeOfferCreate,
    TradeOfferItemRead,
    TradeOfferList,
    TradeOfferRead,
    TradeReviewRead,
    TradeReviewVoteRequest,
    TradeReviewVoteResponse,
    TradeReviewVoteTotalsRead,
)
from collegefootballfantasy_api.app.services.chat_service import (
    create_trade_private_chat_message,
    create_trade_finalized_chat_message,
    create_trade_review_chat_message,
    mark_trade_finalized_chat_message_processed,
    sync_trade_review_chat_message,
)
from collegefootballfantasy_api.app.services.content_moderation import moderate_user_text
from collegefootballfantasy_api.app.services.league_player_history import EVENT_TRADED, EVENT_TRADE_FAILED, append_league_player_event
from collegefootballfantasy_api.app.services.player_trade_value import current_trade_value_snapshot
from collegefootballfantasy_api.app.services.league_weeks import (
    current_cfb_week_state,
    is_cfb_game_week_active,
    next_cfb_trade_process_time,
)
from collegefootballfantasy_api.app.services.notification_service import queue_notification_event
from collegefootballfantasy_api.app.services.notification_events import canonical_event_type
from collegefootballfantasy_api.app.services.player_lock_service import game_starts_for_players
from collegefootballfantasy_api.app.services.roster_legality import (
    assign_best_roster_slot_for_position,
    normalize_roster_slot_limits,
)

TRADE_STATUS_PROPOSED = "proposed"
TRADE_STATUS_ACCEPTED_PENDING = "accepted_pending"
TRADE_STATUS_COMMISSIONER_REVIEW = "commissioner_review"
TRADE_STATUS_PROCESSED = "processed"
TRADE_STATUS_REJECTED = "rejected"
TRADE_STATUS_CANCELLED = "cancelled"
TRADE_STATUS_COUNTERED = "countered"
TRADE_STATUS_VETOED = "vetoed"
TRADE_STATUS_FAILED = "failed"
TRADE_STATUS_EXPIRED = "expired"

OPEN_STATUSES = {TRADE_STATUS_PROPOSED, TRADE_STATUS_COMMISSIONER_REVIEW}
FINAL_STATUSES = {
    TRADE_STATUS_PROCESSED,
    TRADE_STATUS_REJECTED,
    TRADE_STATUS_CANCELLED,
    TRADE_STATUS_COUNTERED,
    TRADE_STATUS_VETOED,
    TRADE_STATUS_FAILED,
    TRADE_STATUS_EXPIRED,
}
STARTER_SLOTS = {"QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K"}
DEFAULT_TRADE_EXPIRATION_DAYS = 7
TRADE_REVIEW_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class TradeRosterMove:
    player_id: int
    source_team_id: int
    target_team_id: int
    slot: str


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


def _load_offer(
    db: Session,
    trade_id: int,
    *,
    for_update: bool = False,
    skip_locked: bool = False,
) -> TradeOffer | None:
    query = (
        db.query(TradeOffer)
        .options(joinedload(TradeOffer.items).joinedload(TradeOfferItem.player), joinedload(TradeOffer.reviews))
        .filter(TradeOffer.id == trade_id)
    )
    if for_update:
        query = query.with_for_update(of=TradeOffer, skip_locked=skip_locked)
    offer = query.first()
    if not offer and not skip_locked:
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
    league_id: int,
    trade_id: int,
    title: str | None = None,
    body: str | None = None,
    payload: dict | None = None,
) -> None:
    if user_id is None:
        return
    event_type = canonical_event_type(alert_type)
    queue_notification_event(
        db,
        league_id=league_id,
        user_id=user_id,
        event_type=event_type,
        event_key=f"{event_type.lower()}:{trade_id}:{user_id}",
        title=title,
        body=body,
        payload={"trade_id": trade_id, **(payload or {})},
    )


def _notify_participants(
    db: Session,
    offer: TradeOffer,
    alert_type: str,
    title: str | None = None,
    body: str | None = None,
) -> None:
    proposing, receiving = _offer_participants(db, offer)
    for user_id in {proposing.owner_user_id, receiving.owner_user_id}:
        _create_alert(
            db,
            user_id=user_id,
            alert_type=alert_type,
            league_id=offer.league_id,
            trade_id=offer.id,
            title=title,
            body=body,
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


def _trade_requires_sunday_processing(db: Session, league: League, offer: TradeOffer, now: datetime) -> bool:
    """Return whether this trade must settle in the next Sunday window.

    Tuesday--Saturday trades can execute immediately only while every involved
    player is more than 24 hours from kickoff. A started or near-kickoff game
    queues the accepted trade for Sunday rather than rejecting it. Sunday and
    Monday are deliberately safe settlement days for completed-game players.
    """
    timezone_name = _trade_timezone(db, league.id)
    if not is_cfb_game_week_active(now, timezone_name):
        return False
    player_ids = _player_ids_for_offer(offer)
    if not player_ids:
        return False
    week_state = current_cfb_week_state(league.season_year, now, timezone_name)
    starts = game_starts_for_players(
        db,
        player_ids=player_ids,
        season=league.season_year,
        week=week_state.week,
    )
    processing_cutoff = _as_utc(now) + timedelta(hours=24)
    return any(start is not None and start <= processing_cutoff for start in starts.values())


def _trade_review_process_after(db: Session, league: League, offer: TradeOffer, now: datetime) -> datetime:
    """Close the mandatory vote window without bypassing game-time locks."""
    review_ends_at = _as_utc(now) + TRADE_REVIEW_WINDOW
    if _trade_requires_sunday_processing(db, league, offer, now):
        review_ends_at = max(review_ends_at, next_cfb_trade_process_time(now, _trade_timezone(db, league.id)))
    return review_ends_at


def _trade_vote_totals(db: Session, offer: TradeOffer) -> TradeReviewVoteTotalsRead:
    votes = (
        db.query(TradeReview.action)
        .filter(TradeReview.trade_offer_id == offer.id, TradeReview.action.in_(("uphold", "veto")))
        .all()
    )
    eligible_voter_count = max(
        1,
        db.query(LeagueMember.user_id)
        .filter(LeagueMember.league_id == offer.league_id)
        .distinct()
        .count(),
    )
    return TradeReviewVoteTotalsRead(
        uphold_count=sum(action == "uphold" for (action,) in votes),
        veto_count=sum(action == "veto" for (action,) in votes),
        veto_threshold=(eligible_voter_count + 1) // 2,
        eligible_voter_count=eligible_voter_count,
    )


def _trade_vote_response(
    db: Session,
    offer: TradeOffer,
    current_user_id: int,
    action: str,
) -> TradeReviewVoteResponse:
    return TradeReviewVoteResponse(
        trade_id=offer.id,
        status=offer.status,
        current_user_vote=action,
        votes=_trade_vote_totals(db, offer),
    )


def _roster_slot_limits(db: Session, league_id: int) -> tuple[dict[str, int], bool]:
    settings = _league_settings(db, league_id)
    raw = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "FLEX": 1,
        "SUPERFLEX": 0,
        "K": 1,
        "BENCH": 5,
        "IR": 1,
    }
    configured = settings.roster_slots_json if settings and settings.roster_slots_json else {}
    raw.update(configured)
    if "BE" in configured and "BENCH" not in configured:
        raw["BENCH"] = configured["BE"]
    return normalize_roster_slot_limits(raw), bool(settings and settings.superflex_enabled)


def _plan_roster_swap(db: Session, offer: TradeOffer) -> tuple[list[RosterEntry], list[TradeRosterMove]]:
    team_ids = sorted({offer.proposing_team_id, offer.receiving_team_id})
    locked_teams = (
        db.query(Team)
        .filter(Team.league_id == offer.league_id, Team.id.in_(team_ids))
        .order_by(Team.id.asc())
        .with_for_update(of=Team)
        .all()
    )
    if {team.id for team in locked_teams} != set(team_ids):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade teams are no longer available")

    player_ids = _player_ids_for_offer(offer)
    all_entries = (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.league_id == offer.league_id, RosterEntry.team_id.in_(team_ids))
        .order_by(RosterEntry.team_id.asc(), RosterEntry.id.asc())
        .with_for_update(of=RosterEntry)
        .all()
    )
    target_by_player: dict[int, int] = {}
    source_by_player: dict[int, int] = {}
    for item in offer.items:
        if item.player_id is None:
            continue
        if item.team_id == offer.proposing_team_id:
            source_by_player[item.player_id] = offer.proposing_team_id
            target_by_player[item.player_id] = offer.receiving_team_id
        elif item.team_id == offer.receiving_team_id:
            source_by_player[item.player_id] = offer.receiving_team_id
            target_by_player[item.player_id] = offer.proposing_team_id
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade item team no longer matches offer")

    outgoing_entries = [entry for entry in all_entries if entry.player_id in target_by_player]
    entry_by_player = {entry.player_id: entry for entry in outgoing_entries}
    if set(entry_by_player) != set(player_ids) or any(
        entry_by_player[player_id].team_id != source_by_player[player_id] for player_id in player_ids
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="one or more players are no longer owned by that team")

    limits, superflex_enabled = _roster_slot_limits(db, offer.league_id)
    simulated_entries = {
        team_id: [entry for entry in all_entries if entry.team_id == team_id and entry.player_id not in target_by_player]
        for team_id in team_ids
    }
    moves: list[TradeRosterMove] = []
    for entry in sorted(outgoing_entries, key=lambda row: row.player_id):
        target_team_id = target_by_player[entry.player_id]
        slot = assign_best_roster_slot_for_position(
            entry.player.position,
            simulated_entries[target_team_id],
            limits,
            superflex_enabled=superflex_enabled,
        )
        if slot is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade would create an illegal roster")
        simulated_entries[target_team_id].append(SimpleNamespace(slot=slot))
        moves.append(
            TradeRosterMove(
                player_id=entry.player_id,
                source_team_id=entry.team_id,
                target_team_id=target_team_id,
                slot=slot,
            )
        )
    return outgoing_entries, moves


def _process_roster_swap(db: Session, offer: TradeOffer, actor_user_id: int | None = None) -> None:
    outgoing_entries, moves = _plan_roster_swap(db, offer)
    player_by_id = {entry.player_id: entry.player for entry in outgoing_entries}
    source_team_by_id = {entry.player_id: db.get(Team, entry.team_id) for entry in outgoing_entries}
    for entry in outgoing_entries:
        db.delete(entry)
    db.flush()
    for move in moves:
        target_team = db.get(Team, move.target_team_id)
        player = player_by_id[move.player_id]
        db.add(
            RosterEntry(
                league_id=offer.league_id,
                team_id=move.target_team_id,
                player_id=move.player_id,
                slot=move.slot,
                status="active",
            )
        )
        transaction = Transaction(
            league_id=offer.league_id,
            team_id=move.target_team_id,
            transaction_type="trade_processed",
            player_id=move.player_id,
            created_by_user_id=actor_user_id,
            reason=f"Trade offer #{offer.id} processed",
        )
        db.add(transaction)
        db.flush()
        append_league_player_event(
            db,
            league=db.get(League, offer.league_id),
            player=player,
            event_type=EVENT_TRADED,
            event_key=f"trade:{offer.id}:player:{move.player_id}",
            occurred_at=_utcnow(),
            from_team=source_team_by_id[move.player_id],
            to_team=target_team,
            manager=db.get(User, actor_user_id) if actor_user_id else None,
            trade_id=offer.id,
            transaction_id=transaction.id,
            metadata={"status": "processed"},
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
        countered_from_trade_id=offer.countered_from_trade_id,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
        items=items,
        reviews=reviews,
    )


def _find_idempotent_offer(
    db: Session,
    *,
    current_user_id: int,
    client_request_id: str | None,
) -> TradeOffer | None:
    if not client_request_id:
        return None
    return (
        db.query(TradeOffer)
        .options(joinedload(TradeOffer.items).joinedload(TradeOfferItem.player), joinedload(TradeOffer.reviews))
        .filter(
            TradeOffer.created_by_user_id == current_user_id,
            TradeOffer.client_request_id == client_request_id,
        )
        .one_or_none()
    )


def _require_matching_idempotent_offer(
    offer: TradeOffer,
    *,
    league_id: int,
    payload: TradeOfferCreate,
    countered_from_trade_id: int | None,
) -> TradeOffer:
    expected_items = sorted(
        (item.team_id, item.player_id, item.draft_pick_id)
        for item in [*payload.give_items, *payload.receive_items]
    )
    actual_items = sorted(
        (item.team_id, item.player_id, item.draft_pick_id)
        for item in offer.items
    )
    if (
        offer.league_id != league_id
        or offer.proposing_team_id != payload.proposing_team_id
        or offer.receiving_team_id != payload.receiving_team_id
        or offer.countered_from_trade_id != countered_from_trade_id
        or offer.message != payload.message
        or actual_items != expected_items
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="client_request_id was already used for a different trade offer",
        )
    return offer


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


def _create_trade_offer_record(
    db: Session,
    *,
    league: League,
    current_user: User,
    payload: TradeOfferCreate,
    proposing: Team,
    receiving: Team,
    countered_from_trade_id: int | None = None,
) -> TradeOffer:
    offer = TradeOffer(
        league_id=league.id,
        proposing_team_id=proposing.id,
        receiving_team_id=receiving.id,
        created_by_user_id=current_user.id,
        status=TRADE_STATUS_PROPOSED,
        message=payload.message,
        client_request_id=payload.client_request_id,
        expires_at=_utcnow() + timedelta(days=DEFAULT_TRADE_EXPIRATION_DAYS),
        countered_from_trade_id=countered_from_trade_id,
    )
    db.add(offer)
    db.flush()
    for item in [*payload.give_items, *payload.receive_items]:
        player_snapshot = current_trade_value_snapshot(db, player_id=item.player_id, season=league.season_year) if item.player_id is not None else None
        db.add(
            TradeOfferItem(
                trade_offer=offer,
                team_id=item.team_id,
                player_id=item.player_id,
                draft_pick_id=item.draft_pick_id,
                item_type="player" if item.player_id is not None else "draft_pick",
                snapshot_json={"trade_value": player_snapshot} if player_snapshot else None,
            )
        )
    db.flush()
    _add_review(db, offer, "proposed", current_user.id, payload.message)
    _create_alert(
        db,
        user_id=receiving.owner_user_id,
        alert_type="TRADE_RECEIVED",
        league_id=league.id,
        trade_id=offer.id,
        payload={"manager_or_team": proposing.name},
    )
    return offer


def create_trade_offer(db: Session, league: League, current_user: User, payload: TradeOfferCreate) -> TradeOfferRead:
    _member_or_404(db, league.id, current_user.id)
    # Store and compare the same canonical note on the initial request and a
    # transport retry.  Without this normalization, a successful request with
    # surrounding whitespace would be persisted as the trimmed value, then a
    # retry of the identical client payload would look like a different offer.
    payload.message = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="trade_message", value=payload.message
    )
    existing = _find_idempotent_offer(
        db,
        current_user_id=current_user.id,
        client_request_id=payload.client_request_id,
    )
    if existing is not None:
        return _serialize_offer(
            _require_matching_idempotent_offer(
                existing,
                league_id=league.id,
                payload=payload,
                countered_from_trade_id=None,
            )
        )
    now = _utcnow()
    _ensure_trade_deadline_open(db, league, now)
    proposing, receiving = _validate_payload(db, league.id, payload)
    _require_team_owner(proposing, current_user)

    try:
        with db.begin_nested():
            offer = _create_trade_offer_record(
                db,
                league=league,
                current_user=current_user,
                payload=payload,
                proposing=proposing,
                receiving=receiving,
            )
            _plan_roster_swap(db, offer)
            create_trade_private_chat_message(db, offer, event_status="proposed")
    except IntegrityError:
        existing = _find_idempotent_offer(
            db,
            current_user_id=current_user.id,
            client_request_id=payload.client_request_id,
        )
        if existing is None:
            raise
        return _serialize_offer(
            _require_matching_idempotent_offer(
                existing,
                league_id=league.id,
                payload=payload,
                countered_from_trade_id=None,
            )
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
    _process_roster_swap(db, offer, actor_user_id=actor_user_id)
    offer.status = TRADE_STATUS_PROCESSED
    offer.accepted_at = offer.accepted_at or now
    offer.process_after = now
    offer.processed_at = now
    offer.failure_reason = None
    _add_review(db, offer, review_action, actor_user_id, review_reason)
    _notify_participants(db, offer, "TRADE_COMPLETED")


def accept_trade_offer(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    payload.reason = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="trade_note", value=payload.reason
    )
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
    # Validate the eventual roster move before opening a public vote. This
    # prevents a league from reviewing an offer that could never be applied.
    _plan_roster_swap(db, offer)
    # Every accepted trade enters the same transparent league-vote window.
    # This replaces both immediate processing and commissioner-only approval.
    offer.status = TRADE_STATUS_ACCEPTED_PENDING
    offer.accepted_at = now
    offer.process_after = _trade_review_process_after(db, league, offer, now)
    _add_review(db, offer, "accepted", current_user.id, payload.reason)
    _notify_participants(
        db,
        offer,
        "TRADE_ACCEPTED_PENDING",
    )
    create_trade_private_chat_message(db, offer, event_status="accepted")
    create_trade_review_chat_message(db, offer)
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def commissioner_approve_trade(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    payload.reason = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="trade_note", value=payload.reason
    )
    _require_commissioner(league, current_user)
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status != TRADE_STATUS_COMMISSIONER_REVIEW:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer is not awaiting commissioner review")
    _validate_offer_ownership(db, offer)
    now = _utcnow()
    _ensure_trade_deadline_open(db, league, now)
    if _trade_requires_sunday_processing(db, league, offer, now):
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
    if offer.status == TRADE_STATUS_ACCEPTED_PENDING:
        _notify_participants(
            db,
            offer,
            "TRADE_ACCEPTED_PENDING",
        )
    if offer.status == TRADE_STATUS_PROCESSED:
        _announce_trade_finalized(db, offer, finalized_at=now)
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def reject_trade_offer(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    payload.reason = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="trade_note", value=payload.reason
    )
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status != TRADE_STATUS_PROPOSED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer is not pending rejection")
    _proposing, receiving = _offer_participants(db, offer)
    _require_team_owner(receiving, current_user)
    offer.status = TRADE_STATUS_REJECTED
    _add_review(db, offer, "rejected", current_user.id, payload.reason)
    _notify_participants(db, offer, "TRADE_DECLINED")
    create_trade_private_chat_message(db, offer, event_status="rejected")
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def cancel_trade_offer(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    payload.reason = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="trade_note", value=payload.reason
    )
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status not in OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer can no longer be cancelled")
    proposing, _receiving = _offer_participants(db, offer)
    _require_team_owner(proposing, current_user)
    offer.status = TRADE_STATUS_CANCELLED
    _add_review(db, offer, "cancelled", current_user.id, payload.reason)
    _notify_participants(db, offer, "TRADE_CANCELED")
    create_trade_private_chat_message(db, offer, event_status="cancelled")
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def counter_trade_offer(
    db: Session,
    league: League,
    trade_id: int,
    current_user: User,
    payload: TradeOfferCounterCreate,
) -> TradeOfferRead:
    payload.message = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="trade_message", value=payload.message
    )
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    _member_or_404(db, league.id, current_user.id)
    existing = _find_idempotent_offer(
        db,
        current_user_id=current_user.id,
        client_request_id=payload.client_request_id,
    )
    if existing is not None:
        return _serialize_offer(
            _require_matching_idempotent_offer(
                existing,
                league_id=league.id,
                payload=payload,
                countered_from_trade_id=offer.id,
            )
        )
    if offer.status != TRADE_STATUS_PROPOSED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer is not pending a counter")
    now = _utcnow()
    _ensure_not_expired(offer, now)
    _ensure_trade_deadline_open(db, league, now)
    _proposing, receiving = _offer_participants(db, offer)
    _require_team_owner(receiving, current_user)
    proposing, counter_receiving = _validate_payload(db, league.id, payload)
    if proposing.id != offer.receiving_team_id or counter_receiving.id != offer.proposing_team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="counter offer must reverse the original trade participants",
        )
    _require_team_owner(proposing, current_user)

    try:
        with db.begin_nested():
            replacement = _create_trade_offer_record(
                db,
                league=league,
                current_user=current_user,
                payload=payload,
                proposing=proposing,
                receiving=counter_receiving,
                countered_from_trade_id=offer.id,
            )
            _plan_roster_swap(db, replacement)
            offer.status = TRADE_STATUS_COUNTERED
            _add_review(db, offer, "countered", current_user.id, payload.message)
            _notify_participants(db, offer, "TRADE_COUNTERED", "Trade Countered", "A replacement trade offer was sent.")
            create_trade_private_chat_message(db, offer, event_status="countered")
            create_trade_private_chat_message(db, replacement, event_status="proposed")
    except IntegrityError:
        existing = _find_idempotent_offer(
            db,
            current_user_id=current_user.id,
            client_request_id=payload.client_request_id,
        )
        if existing is None:
            raise
        return _serialize_offer(
            _require_matching_idempotent_offer(
                existing,
                league_id=league.id,
                payload=payload,
                countered_from_trade_id=offer.id,
            )
        )
    db.commit()
    return _serialize_offer(_load_offer(db, replacement.id))


def commissioner_veto_trade(db: Session, league: League, trade_id: int, current_user: User, payload: TradeActionRequest) -> TradeOfferRead:
    payload.reason = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="trade_note", value=payload.reason
    )
    _require_commissioner(league, current_user)
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status not in {TRADE_STATUS_COMMISSIONER_REVIEW, TRADE_STATUS_ACCEPTED_PENDING}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer is not reviewable")
    offer.status = TRADE_STATUS_VETOED
    _add_review(db, offer, "vetoed", current_user.id, payload.reason)
    _notify_participants(db, offer, "TRADE_VETOED", "Trade Vetoed", "A trade offer was vetoed.")
    create_trade_private_chat_message(db, offer, event_status="vetoed")
    db.commit()
    return _serialize_offer(_load_offer(db, offer.id))


def vote_on_trade_review(
    db: Session,
    league: League,
    trade_id: int,
    current_user: User,
    payload: TradeReviewVoteRequest,
) -> TradeReviewVoteResponse:
    """Record one league-member vote and veto immediately at the threshold."""
    _member_or_404(db, league.id, current_user.id)
    offer = _load_offer(db, trade_id, for_update=True)
    if offer.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    if offer.status != TRADE_STATUS_ACCEPTED_PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade review is no longer open")

    existing_vote = (
        db.query(TradeReview)
        .filter(
            TradeReview.trade_offer_id == offer.id,
            TradeReview.reviewer_user_id == current_user.id,
            TradeReview.action.in_(("uphold", "veto")),
        )
        .one_or_none()
    )
    if existing_vote is not None:
        if existing_vote.action != payload.action:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade vote has already been cast")
        return _trade_vote_response(db, offer, current_user.id, existing_vote.action)

    _add_review(db, offer, payload.action, current_user.id)
    db.flush()
    totals = _trade_vote_totals(db, offer)
    if totals.veto_count >= totals.veto_threshold:
        offer.status = TRADE_STATUS_VETOED
        _add_review(db, offer, "vetoed", None, "league veto threshold reached")
        _notify_participants(db, offer, "TRADE_VETOED", "Trade Vetoed", "League veto threshold reached.")
        create_trade_private_chat_message(db, offer, event_status="vetoed")
    sync_trade_review_chat_message(db, offer)
    db.commit()
    return _trade_vote_response(db, _load_offer(db, offer.id), current_user.id, payload.action)


def expire_trade_offers_once(db: Session, now: datetime | None = None) -> dict[str, int]:
    current = _as_utc(now or _utcnow())
    offer_ids = [
        offer_id
        for (offer_id,) in (
            db.query(TradeOffer.id)
            .filter(TradeOffer.status.in_(OPEN_STATUSES))
            .filter(TradeOffer.expires_at.isnot(None), TradeOffer.expires_at <= current)
            .order_by(TradeOffer.expires_at.asc(), TradeOffer.id.asc())
            .all()
        )
    ]
    expired = 0
    for offer_id in offer_ids:
        offer = _load_offer(db, offer_id, for_update=True, skip_locked=True)
        if offer is None or offer.status not in OPEN_STATUSES or offer.expires_at is None or _as_utc(offer.expires_at) > current:
            continue
        offer.status = TRADE_STATUS_EXPIRED
        _add_review(db, offer, "expired", None, "trade offer expired")
        _notify_participants(db, offer, "TRADE_EXPIRED")
        create_trade_private_chat_message(db, offer, event_status="expired")
        db.commit()
        expired += 1
    return {"expired": expired}


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
        # A league-wide game window is not itself a reason to hold a completed
        # review.  Only a traded player's started/near-kickoff game may defer
        # this transfer; otherwise a no-veto trade settles when its 24-hour
        # vote window ends.
        if _trade_requires_sunday_processing(db, league, offer, current):
            offer.process_after = next_cfb_trade_process_time(current, _trade_timezone(db, league.id))
            sync_trade_review_chat_message(db, offer)
            db.commit()
            continue
        try:
            with db.begin_nested():
                _ensure_trade_deadline_open(db, league, current)
                _validate_offer_ownership(db, offer)
                _complete_accepted_trade(
                    db,
                    league=league,
                    offer=offer,
                    actor_user_id=None,
                    now=current,
                    review_action="processed",
                )
                _announce_trade_finalized(db, offer, finalized_at=current)
                mark_trade_finalized_chat_message_processed(db, offer)
                sync_trade_review_chat_message(db, offer)
            processed += 1
        except Exception as exc:
            offer.status = TRADE_STATUS_FAILED
            offer.failure_reason = str(exc.detail) if isinstance(exc, HTTPException) else "trade processing failed"
            for item in offer.items:
                if item.player is None:
                    continue
                append_league_player_event(
                    db,
                    league=league,
                    player=item.player,
                    event_type=EVENT_TRADE_FAILED,
                    event_key=f"trade-failed:{offer.id}:player:{item.player.id}",
                    occurred_at=current,
                    fantasy_team=_team_or_404(db, league.id, item.team_id),
                    trade_id=offer.id,
                    metadata={"reason": offer.failure_reason},
                )
            _add_review(db, offer, "failed", None, offer.failure_reason)
            _notify_participants(db, offer, "TRADE_FAILED", "Trade Failed", offer.failure_reason)
            create_trade_private_chat_message(db, offer, event_status="failed")
            failed += 1
        db.commit()
    return {"processed": processed, "failed": failed}
