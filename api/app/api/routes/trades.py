from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import (
    get_current_user,
    get_league_or_404,
    require_commissioner,
    require_league_member,
)
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.defense_vs_position import DefenseVsPosition
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.trade import (
    TradeOfferActionResponse,
    TradeOfferList,
    TradeOfferSummary,
    TradeAnalyzeRequest,
    TradeAnalyzeResponse,
    TradeProposalRequest,
    TradeProposalResponse,
)
from collegefootballfantasy_api.app.services.admin_actions import append_admin_action
from collegefootballfantasy_api.app.services.idempotency import (
    begin_idempotent_request,
    complete_idempotent_request,
    fail_idempotent_request,
)
from collegefootballfantasy_api.app.services.matchup_grades import build_matchup_row

router = APIRouter()

DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BE": 4,
    "IR": 1,
}

BENCH_DISTRIBUTION = {
    "QB": 0.10,
    "RB": 0.38,
    "WR": 0.38,
    "TE": 0.09,
    "K": 0.05,
}

GRADE_MULTIPLIER = {
    "A+": 1.08,
    "A": 1.05,
    "B": 1.02,
    "C": 1.0,
    "D": 0.97,
    "F": 0.94,
}
TRADE_OPEN_STATUSES = {"open"}
TRADE_PENDING_REVIEW_STATUSES = {"pending_review"}
TRADE_RESOLVED_STATUSES = {"accepted", "rejected", "cancelled", "expired", "vetoed"}
DEFAULT_TRADE_EXPIRY_HOURS = 48


def _unique_player_ids(player_ids: list[int]) -> list[int]:
    return list(dict.fromkeys(player_ids))


def _utc_now() -> datetime:
    return datetime.utcnow()


def _auto_expire_trade_offer(offer: TradeOffer) -> bool:
    if offer.status not in TRADE_OPEN_STATUSES:
        return False
    if offer.expires_at and offer.expires_at <= _utc_now():
        offer.status = "expired"
        offer.responded_at = _utc_now()
        return True
    return False


def _trade_offer_side_ids(db: Session, offer_id: int, side: str) -> list[int]:
    rows = (
        db.query(TradeOfferItem.player_id)
        .filter(TradeOfferItem.trade_offer_id == offer_id, TradeOfferItem.side == side)
        .all()
    )
    return [int(row[0]) for row in rows]


def _serialize_trade_offer(db: Session, offer: TradeOffer) -> TradeOfferSummary:
    give_ids = _trade_offer_side_ids(db, offer.id, "give")
    receive_ids = _trade_offer_side_ids(db, offer.id, "receive")
    return TradeOfferSummary(
        proposal_ref=offer.proposal_ref,
        league_id=offer.league_id,
        from_team_id=offer.from_team_id,
        to_team_id=offer.to_team_id,
        from_user_id=offer.from_user_id,
        to_user_id=offer.to_user_id,
        status=offer.status,
        review_status=offer.review_status,
        review_mode=offer.review_mode,
        note=offer.note,
        expires_at=offer.expires_at.isoformat() if offer.expires_at else None,
        responded_at=offer.responded_at.isoformat() if offer.responded_at else None,
        give_ids=give_ids,
        receive_ids=receive_ids,
        created_at=offer.created_at.isoformat(),
        updated_at=offer.updated_at.isoformat(),
    )


def _record_trade_transaction(
    db: Session,
    *,
    league_id: int,
    team_id: int,
    created_by_user_id: int,
    transaction_type: str,
    player_id: int | None = None,
    related_player_id: int | None = None,
    reason: str | None = None,
) -> None:
    row = Transaction(
        league_id=league_id,
        team_id=team_id,
        transaction_type=transaction_type,
        player_id=player_id,
        related_player_id=related_player_id,
        created_by_user_id=created_by_user_id,
        reason=reason,
    )
    db.add(row)


def _load_trade_offer_for_member(
    db: Session,
    *,
    proposal_ref: str,
    current_user: User,
) -> TradeOffer:
    offer = db.query(TradeOffer).filter(TradeOffer.proposal_ref == proposal_ref).first()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
    league = get_league_or_404(db, offer.league_id)
    require_league_member(db, league.id, current_user)
    if _auto_expire_trade_offer(offer):
        db.add(offer)
        db.commit()
        db.refresh(offer)
    return offer


def _execute_trade_accept(
    db: Session,
    *,
    offer: TradeOffer,
    acted_by_user: User,
) -> None:
    give_ids = _trade_offer_side_ids(db, offer.id, "give")
    receive_ids = _trade_offer_side_ids(db, offer.id, "receive")
    if not give_ids or not receive_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer has no player items")
    if len(give_ids) != len(receive_ids):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade offer side counts are invalid")

    from_entries = (
        db.query(RosterEntry)
        .filter(RosterEntry.team_id == offer.from_team_id, RosterEntry.player_id.in_(give_ids))
        .all()
    )
    to_entries = (
        db.query(RosterEntry)
        .filter(RosterEntry.team_id == offer.to_team_id, RosterEntry.player_id.in_(receive_ids))
        .all()
    )
    if len({row.player_id for row in from_entries}) != len(give_ids):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade invalid: sender roster changed")
    if len({row.player_id for row in to_entries}) != len(receive_ids):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade invalid: recipient roster changed")

    for row in from_entries:
        row.team_id = offer.to_team_id
        row.slot = "BENCH"
        db.add(row)
    for row in to_entries:
        row.team_id = offer.from_team_id
        row.slot = "BENCH"
        db.add(row)

    for player_id in give_ids:
        _record_trade_transaction(
            db,
            league_id=offer.league_id,
            team_id=offer.from_team_id,
            transaction_type="trade_out",
            created_by_user_id=acted_by_user.id,
            player_id=player_id,
            reason=f"{offer.proposal_ref} accepted",
        )
        _record_trade_transaction(
            db,
            league_id=offer.league_id,
            team_id=offer.to_team_id,
            transaction_type="trade_in",
            created_by_user_id=acted_by_user.id,
            player_id=player_id,
            reason=f"{offer.proposal_ref} accepted",
        )
    for player_id in receive_ids:
        _record_trade_transaction(
            db,
            league_id=offer.league_id,
            team_id=offer.to_team_id,
            transaction_type="trade_out",
            created_by_user_id=acted_by_user.id,
            player_id=player_id,
            reason=f"{offer.proposal_ref} accepted",
        )
        _record_trade_transaction(
            db,
            league_id=offer.league_id,
            team_id=offer.from_team_id,
            transaction_type="trade_in",
            created_by_user_id=acted_by_user.id,
            player_id=player_id,
            reason=f"{offer.proposal_ref} accepted",
        )


def _normalize_roster_slots(roster_slots: dict[str, int] | None) -> dict[str, int]:
    return DEFAULT_ROSTER_SLOTS.copy()


def _replacement_index(pos: str, league_size: int, roster_slots: dict[str, int]) -> int:
    starters = roster_slots.get(pos, 0) * league_size
    bench_slots = (roster_slots.get("BE", 0) + roster_slots.get("IR", 0)) * league_size
    bench_share = bench_slots * BENCH_DISTRIBUTION.get(pos, 0.0)
    return max(1, round(starters + bench_share))


def _build_replacement_by_pos(
    db: Session, season: int, week: int, league_size: int, roster_slots: dict[str, int]
) -> dict[str, float]:
    rows = (
        db.query(WeeklyProjection, Player)
        .join(Player, WeeklyProjection.player_id == Player.id)
        .filter(WeeklyProjection.season == season, WeeklyProjection.week == week)
        .all()
    )
    points_by_pos: dict[str, list[float]] = {}
    for projection, player in rows:
        pos = player.position.upper()
        if pos not in {"QB", "RB", "WR", "TE", "K"}:
            continue
        points_by_pos.setdefault(pos, []).append(projection.fantasy_points or 0.0)

    replacement_by_pos: dict[str, float] = {}
    for pos, values in points_by_pos.items():
        values_sorted = sorted(values, reverse=True)
        index = _replacement_index(pos, league_size, roster_slots) - 1
        index = max(0, min(index, len(values_sorted) - 1))
        replacement_by_pos[pos] = values_sorted[index] if values_sorted else 0.0
    return replacement_by_pos


def _injury_multiplier(status: str | None) -> float:
    if not status:
        return 1.0
    status = status.upper()
    if status == "OUT":
        return 0.4
    if status == "DOUBTFUL":
        return 0.6
    if status == "QUESTIONABLE":
        return 0.8
    if status == "PROBABLE":
        return 0.95
    return 1.0


def _schedule_multiplier(
    db: Session, player: Player, season: int, week: int, weeks: int = 4
) -> float:
    games = (
        db.query(Game)
        .filter(Game.season == season, Game.week >= week)
        .filter(or_(Game.home_team == player.school, Game.away_team == player.school))
        .order_by(Game.week.asc())
        .limit(weeks)
        .all()
    )
    if not games:
        return 1.0

    multipliers: list[float] = []
    for game in games:
        opponent = game.away_team if game.home_team == player.school else game.home_team
        cached = (
            db.query(DefenseVsPosition)
            .filter(
                DefenseVsPosition.team_name == opponent,
                DefenseVsPosition.season == season,
                DefenseVsPosition.week == game.week,
                DefenseVsPosition.position == player.position.upper(),
            )
            .first()
        )
        defense = (
            db.query(DefenseRating)
            .filter(DefenseRating.team_name == opponent, DefenseRating.season == season, DefenseRating.week == game.week)
            .first()
        )
        row = build_matchup_row(opponent, season, game.week, player.position, defense, cached)
        multipliers.append(GRADE_MULTIPLIER.get(row["grade"], 1.0))
    return round(sum(multipliers) / len(multipliers), 3) if multipliers else 1.0


def _player_value(
    player: Player,
    projection: WeeklyProjection | None,
    replacement_by_pos: dict[str, float],
    injury_status: str | None,
    schedule_mult: float,
) -> float:
    points = projection.fantasy_points if projection else 0.0
    replacement = replacement_by_pos.get(player.position.upper(), 0.0)
    points_above = points - replacement
    scarcity_bonus = max(0.0, points_above) * 0.5
    injury_mult = _injury_multiplier(injury_status)
    value = (points + scarcity_bonus) * injury_mult * schedule_mult
    return round(value, 2)


@router.post("/analyze", response_model=TradeAnalyzeResponse)
def analyze_trade(payload: TradeAnalyzeRequest, db: Session = Depends(get_db)) -> TradeAnalyzeResponse:
    if not payload.receive_ids or not payload.give_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="receive_ids and give_ids required")

    players = db.query(Player).filter(Player.id.in_(payload.receive_ids + payload.give_ids)).all()
    player_by_id = {player.id: player for player in players}

    projections = (
        db.query(WeeklyProjection)
        .filter(WeeklyProjection.season == payload.season, WeeklyProjection.week == payload.week)
        .filter(WeeklyProjection.player_id.in_(payload.receive_ids + payload.give_ids))
        .all()
    )
    proj_by_id = {proj.player_id: proj for proj in projections}

    injuries = (
        db.query(Injury)
        .filter(Injury.season == payload.season, Injury.week == payload.week)
        .filter(Injury.player_id.in_(payload.receive_ids + payload.give_ids))
        .all()
    )
    injury_by_id = {inj.player_id: inj for inj in injuries}

    roster_slots = _normalize_roster_slots(payload.roster_slots)
    replacement_by_pos = _build_replacement_by_pos(
        db, payload.season, payload.week, payload.league_size, roster_slots
    )

    receive_value = 0.0
    for pid in payload.receive_ids:
        player = player_by_id.get(pid)
        if player:
            injury_status = injury_by_id.get(pid).status if injury_by_id.get(pid) else None
            schedule_mult = _schedule_multiplier(db, player, payload.season, payload.week)
            receive_value += _player_value(
                player,
                proj_by_id.get(pid),
                replacement_by_pos,
                injury_status,
                schedule_mult,
            )

    give_value = 0.0
    for pid in payload.give_ids:
        player = player_by_id.get(pid)
        if player:
            injury_status = injury_by_id.get(pid).status if injury_by_id.get(pid) else None
            schedule_mult = _schedule_multiplier(db, player, payload.season, payload.week)
            give_value += _player_value(
                player,
                proj_by_id.get(pid),
                replacement_by_pos,
                injury_status,
                schedule_mult,
            )

    delta = receive_value - give_value
    verdict = "Even"
    if give_value > 0:
        delta_pct = delta / give_value
        if delta_pct >= 0.08:
            verdict = "Strong Win"
        elif delta_pct >= 0.03:
            verdict = "Slight Win"
        elif delta_pct <= -0.08:
            verdict = "Strong Loss"
        elif delta_pct <= -0.03:
            verdict = "Slight Loss"

    return TradeAnalyzeResponse(
        receive_value=round(receive_value, 2),
        give_value=round(give_value, 2),
        delta=round(delta, 2),
        verdict=verdict,
    )


@router.post("/propose", response_model=TradeProposalResponse, status_code=status.HTTP_201_CREATED)
def propose_trade(
    payload: TradeProposalRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeProposalResponse:
    if payload.from_team_id == payload.to_team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade teams must be different")

    give_ids = _unique_player_ids(payload.give_ids)
    receive_ids = _unique_player_ids(payload.receive_ids)
    if not give_ids or not receive_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade requires players on both sides")
    if len(give_ids) != len(receive_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="trade must include an equal number of players on each side",
        )

    note = payload.note.strip() if payload.note else ""
    if len(note) > 300:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade note must be 300 characters or fewer")

    league = get_league_or_404(db, payload.league_id)
    require_league_member(db, league.id, current_user)
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    review_mode = settings_row.trade_review_type if settings_row else "commissioner"

    from_team = db.get(Team, payload.from_team_id)
    to_team = db.get(Team, payload.to_team_id)
    if not from_team or from_team.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="from_team not found in this league")
    if not to_team or to_team.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="to_team not found in this league")
    if from_team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team ownership required for trade proposals")
    if to_team.owner_user_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade target team does not have an owner yet")
    if to_team.owner_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot trade with your own team")

    give_entries = (
        db.query(RosterEntry)
        .filter(RosterEntry.team_id == from_team.id, RosterEntry.player_id.in_(give_ids))
        .all()
    )
    receive_entries = (
        db.query(RosterEntry)
        .filter(RosterEntry.team_id == to_team.id, RosterEntry.player_id.in_(receive_ids))
        .all()
    )
    if len({row.player_id for row in give_entries}) != len(give_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="one or more selected give players are no longer on your roster",
        )
    if len({row.player_id for row in receive_entries}) != len(receive_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="one or more selected receive players are no longer on the target roster",
        )

    players = (
        db.query(Player)
        .filter(Player.id.in_(give_ids + receive_ids))
        .all()
    )
    player_name_by_id = {player.id: player.name for player in players}
    give_names = [player_name_by_id.get(player_id, f"Player {player_id}") for player_id in give_ids]
    receive_names = [player_name_by_id.get(player_id, f"Player {player_id}") for player_id in receive_ids]

    idem = begin_idempotent_request(
        db,
        scope=f"league:{league.id}:trades:propose:from:{payload.from_team_id}",
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)

    try:
        proposal_ref = f"TR-{uuid4().hex[:8].upper()}"
        trade_offer = TradeOffer(
            proposal_ref=proposal_ref,
            league_id=league.id,
            from_team_id=from_team.id,
            to_team_id=to_team.id,
            from_user_id=current_user.id,
            to_user_id=to_team.owner_user_id,
            status="open",
            review_status="pending",
            review_mode=review_mode,
            note=note or None,
            expires_at=datetime.utcnow().replace(microsecond=0) + timedelta(hours=DEFAULT_TRADE_EXPIRY_HOURS),
        )
        db.add(trade_offer)
        db.flush()
        for player_id in give_ids:
            db.add(TradeOfferItem(trade_offer_id=trade_offer.id, player_id=player_id, side="give"))
        for player_id in receive_ids:
            db.add(TradeOfferItem(trade_offer_id=trade_offer.id, player_id=player_id, side="receive"))

        trade_summary = (
            f"{from_team.name} sends {', '.join(give_names)} for {', '.join(receive_names)}."
        )
        if note:
            trade_summary = f"{trade_summary} Note: {note}"

        recipient_alert = NotificationLog(
            user_id=to_team.owner_user_id,
            user_key=str(to_team.owner_user_id),
            alert_type="TRADE_SENT",
            title=f"New trade offer from {from_team.name}",
            body=trade_summary,
            payload={
                "proposal_ref": proposal_ref,
                "league_id": league.id,
                "from_team_id": from_team.id,
                "to_team_id": to_team.id,
                "give_ids": give_ids,
                "receive_ids": receive_ids,
                "player_id": receive_ids[0],
                "path": f"/trade/{league.id}",
            },
            sent_at=datetime.utcnow(),
        )
        sender_alert = NotificationLog(
            user_id=current_user.id,
            user_key=str(current_user.id),
            alert_type="TRADE",
            title=f"Trade offer sent to {to_team.name}",
            body=trade_summary,
            payload={
                "proposal_ref": proposal_ref,
                "league_id": league.id,
                "from_team_id": from_team.id,
                "to_team_id": to_team.id,
                "give_ids": give_ids,
                "receive_ids": receive_ids,
                "player_id": give_ids[0],
                "path": f"/trade/{league.id}",
            },
            sent_at=datetime.utcnow(),
        )
        db.add(recipient_alert)
        db.add(sender_alert)
        append_admin_action(
            db,
            league_id=league.id,
            actor_user_id=current_user.id,
            action_type="trade.proposed",
            target_type="trade_offer",
            target_id=trade_offer.id,
            metadata={
                "proposal_ref": proposal_ref,
                "from_team_id": from_team.id,
                "to_team_id": to_team.id,
                "give_ids": give_ids,
                "receive_ids": receive_ids,
                "review_mode": review_mode,
            },
        )
        response_payload = TradeProposalResponse(
            proposal_ref=proposal_ref,
            message=f"Trade offer sent to {to_team.name}.",
        ).model_dump(mode="json")
        complete_idempotent_request(
            db,
            start=idem,
            response_status_code=status.HTTP_201_CREATED,
            response_payload=response_payload,
        )
        db.commit()
        return response_payload
    except Exception:
        fail_idempotent_request(db, start=idem)
        db.commit()
        raise


@router.get("/{league_id}/offers", response_model=TradeOfferList)
def list_trade_offers(
    league_id: int,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeOfferList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)

    query = (
        db.query(TradeOffer)
        .filter(TradeOffer.league_id == league.id)
        .order_by(TradeOffer.created_at.desc(), TradeOffer.id.desc())
    )
    if status_filter:
        query = query.filter(TradeOffer.status == status_filter.strip().lower())
    rows = query.offset(max(0, offset)).limit(max(1, min(limit, 200))).all()
    total = (
        db.query(TradeOffer)
        .filter(TradeOffer.league_id == league.id)
        .count()
    )
    payload = [_serialize_trade_offer(db, row) for row in rows]
    return TradeOfferList(data=payload, total=total, limit=max(1, min(limit, 200)), offset=max(0, offset))


@router.post("/{proposal_ref}/accept", response_model=TradeOfferActionResponse)
def accept_trade_offer(
    proposal_ref: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeOfferActionResponse:
    offer = _load_trade_offer_for_member(db, proposal_ref=proposal_ref, current_user=current_user)
    if offer.status not in TRADE_OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade is already {offer.status}")
    if current_user.id != offer.to_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the receiving manager can accept")
    idem = begin_idempotent_request(
        db,
        scope=f"trade:{proposal_ref}:accept",
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)
    try:
        with db.begin_nested():
            offer_locked = db.query(TradeOffer).filter(TradeOffer.id == offer.id).with_for_update().first()
            if not offer_locked:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
            if _auto_expire_trade_offer(offer_locked):
                db.add(offer_locked)
                db.flush()
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trade has expired")
            if offer_locked.status not in TRADE_OPEN_STATUSES:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade is already {offer_locked.status}")
            review_mode = (offer_locked.review_mode or "commissioner").strip().lower()
            offer_locked.responded_at = _utc_now()
            if review_mode in {"none", "instant", "auto"}:
                _execute_trade_accept(db, offer=offer_locked, acted_by_user=current_user)
                offer_locked.status = "accepted"
                offer_locked.review_status = "accepted"
            else:
                offer_locked.status = "pending_review"
                offer_locked.review_status = "pending_commissioner"
            db.add(offer_locked)

        response = (
            TradeOfferActionResponse(
                proposal_ref=proposal_ref,
                status="accepted",
                message="Trade accepted and rosters updated.",
            )
            if offer.review_mode and offer.review_mode.strip().lower() in {"none", "instant", "auto"}
            else TradeOfferActionResponse(
                proposal_ref=proposal_ref,
                status="pending_review",
                message="Trade accepted and is pending commissioner review.",
            )
        )
        append_admin_action(
            db,
            league_id=offer.league_id,
            actor_user_id=current_user.id,
            action_type="trade.accepted",
            target_type="trade_offer",
            target_id=offer.id,
            metadata={"proposal_ref": proposal_ref, "result_status": response.status},
        )
        payload = response.model_dump(mode="json")
        complete_idempotent_request(
            db,
            start=idem,
            response_status_code=status.HTTP_200_OK,
            response_payload=payload,
        )
        db.commit()
        return payload
    except Exception:
        fail_idempotent_request(db, start=idem)
        db.commit()
        raise


@router.post("/{proposal_ref}/review/approve", response_model=TradeOfferActionResponse)
def approve_trade_offer(
    proposal_ref: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeOfferActionResponse:
    offer = _load_trade_offer_for_member(db, proposal_ref=proposal_ref, current_user=current_user)
    require_commissioner(db, offer.league_id, current_user)
    if offer.status not in TRADE_PENDING_REVIEW_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade is already {offer.status}")
    idem = begin_idempotent_request(
        db,
        scope=f"trade:{proposal_ref}:review:approve",
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)
    try:
        with db.begin_nested():
            offer_locked = db.query(TradeOffer).filter(TradeOffer.id == offer.id).with_for_update().first()
            if not offer_locked:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trade offer not found")
            if offer_locked.status not in TRADE_PENDING_REVIEW_STATUSES:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade is already {offer_locked.status}")
            _execute_trade_accept(db, offer=offer_locked, acted_by_user=current_user)
            offer_locked.status = "accepted"
            offer_locked.review_status = "approved"
            offer_locked.responded_at = _utc_now()
            db.add(offer_locked)
        response = TradeOfferActionResponse(
            proposal_ref=proposal_ref,
            status="accepted",
            message="Trade approved and rosters updated.",
        )
        append_admin_action(
            db,
            league_id=offer.league_id,
            actor_user_id=current_user.id,
            action_type="trade.review.approved",
            target_type="trade_offer",
            target_id=offer.id,
            metadata={"proposal_ref": proposal_ref},
        )
        payload = response.model_dump(mode="json")
        complete_idempotent_request(
            db,
            start=idem,
            response_status_code=status.HTTP_200_OK,
            response_payload=payload,
        )
        db.commit()
        return payload
    except Exception:
        fail_idempotent_request(db, start=idem)
        db.commit()
        raise


@router.post("/{proposal_ref}/review/reject", response_model=TradeOfferActionResponse)
def reject_trade_offer_review(
    proposal_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeOfferActionResponse:
    offer = _load_trade_offer_for_member(db, proposal_ref=proposal_ref, current_user=current_user)
    require_commissioner(db, offer.league_id, current_user)
    if offer.status not in TRADE_PENDING_REVIEW_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade is already {offer.status}")

    offer.status = "vetoed"
    offer.review_status = "rejected"
    offer.responded_at = _utc_now()
    db.add(offer)
    append_admin_action(
        db,
        league_id=offer.league_id,
        actor_user_id=current_user.id,
        action_type="trade.review.rejected",
        target_type="trade_offer",
        target_id=offer.id,
        metadata={"proposal_ref": proposal_ref},
    )
    db.commit()

    return TradeOfferActionResponse(
        proposal_ref=proposal_ref,
        status="vetoed",
        message="Trade rejected by commissioner.",
    )


@router.post("/{proposal_ref}/review/veto", response_model=TradeOfferActionResponse)
def veto_trade_offer_review(
    proposal_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeOfferActionResponse:
    return reject_trade_offer_review(
        proposal_ref=proposal_ref,
        db=db,
        current_user=current_user,
    )


@router.post("/{proposal_ref}/review/clear", response_model=TradeOfferActionResponse)
def clear_trade_review(
    proposal_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeOfferActionResponse:
    offer = _load_trade_offer_for_member(db, proposal_ref=proposal_ref, current_user=current_user)
    require_commissioner(db, offer.league_id, current_user)
    if offer.status not in TRADE_RESOLVED_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade is {offer.status}; cannot clear review")

    offer.review_status = "cleared"
    db.add(offer)
    append_admin_action(
        db,
        league_id=offer.league_id,
        actor_user_id=current_user.id,
        action_type="trade.review.cleared",
        target_type="trade_offer",
        target_id=offer.id,
        metadata={"proposal_ref": proposal_ref, "status": offer.status},
    )
    db.commit()

    return TradeOfferActionResponse(
        proposal_ref=proposal_ref,
        status=offer.status,
        message="Trade review status cleared.",
    )


@router.post("/{proposal_ref}/reject", response_model=TradeOfferActionResponse)
def reject_trade_offer(
    proposal_ref: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeOfferActionResponse:
    offer = _load_trade_offer_for_member(db, proposal_ref=proposal_ref, current_user=current_user)
    if offer.status not in TRADE_OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade is already {offer.status}")
    if current_user.id != offer.to_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the receiving manager can reject")
    idem = begin_idempotent_request(
        db,
        scope=f"trade:{proposal_ref}:reject",
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)
    try:
        offer.status = "rejected"
        offer.review_status = "rejected"
        offer.responded_at = _utc_now()
        db.add(offer)
        append_admin_action(
            db,
            league_id=offer.league_id,
            actor_user_id=current_user.id,
            action_type="trade.rejected",
            target_type="trade_offer",
            target_id=offer.id,
            metadata={"proposal_ref": proposal_ref},
        )
        payload = TradeOfferActionResponse(
            proposal_ref=proposal_ref,
            status="rejected",
            message="Trade rejected.",
        ).model_dump(mode="json")
        complete_idempotent_request(
            db,
            start=idem,
            response_status_code=status.HTTP_200_OK,
            response_payload=payload,
        )
        db.commit()
        return payload
    except Exception:
        fail_idempotent_request(db, start=idem)
        db.commit()
        raise


@router.post("/{proposal_ref}/cancel", response_model=TradeOfferActionResponse)
def cancel_trade_offer(
    proposal_ref: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TradeOfferActionResponse:
    offer = _load_trade_offer_for_member(db, proposal_ref=proposal_ref, current_user=current_user)
    if offer.status not in TRADE_OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"trade is already {offer.status}")
    if current_user.id != offer.from_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the sending manager can cancel")
    idem = begin_idempotent_request(
        db,
        scope=f"trade:{proposal_ref}:cancel",
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)
    try:
        offer.status = "cancelled"
        offer.review_status = "cancelled"
        offer.responded_at = _utc_now()
        db.add(offer)
        append_admin_action(
            db,
            league_id=offer.league_id,
            actor_user_id=current_user.id,
            action_type="trade.cancelled",
            target_type="trade_offer",
            target_id=offer.id,
            metadata={"proposal_ref": proposal_ref},
        )
        payload = TradeOfferActionResponse(
            proposal_ref=proposal_ref,
            status="cancelled",
            message="Trade cancelled.",
        ).model_dump(mode="json")
        complete_idempotent_request(
            db,
            start=idem,
            response_status_code=status.HTTP_200_OK,
            response_payload=payload,
        )
        db.commit()
        return payload
    except Exception:
        fail_idempotent_request(db, start=idem)
        db.commit()
        raise
