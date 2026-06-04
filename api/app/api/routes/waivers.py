from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.app.api.deps import (
    get_current_user,
    get_league_or_404,
    require_commissioner,
    require_league_member,
    require_team_owner,
)
from api.app.db.session import get_db
from api.app.models.league_settings import LeagueSettings
from api.app.models.notification import NotificationLog
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.models.transaction import Transaction
from api.app.models.user import User
from api.app.models.waiver_claim import WaiverClaim
from api.app.schemas.waiver import (
    WaiverClaimCreateRequest,
    WaiverClaimList,
    WaiverClaimRead,
    WaiverProcessRequest,
    WaiverProcessResponse,
    WaiverProcessResultRow,
)
from api.app.services.admin_actions import append_admin_action
from api.app.services.event_stream import append_league_event
from api.app.services.idempotency import (
    begin_idempotent_request,
    complete_idempotent_request,
    fail_idempotent_request,
    get_completed_idempotent_response,
)
from api.app.services.waiver_engine import process_pending_waiver_claims

router = APIRouter()

DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BENCH": 4,
    "IR": 1,
}

PENDING_STATUSES = {"pending"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _league_settings(db: Session, league_id: int) -> LeagueSettings:
    row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return row


def _waiver_mode(settings_row: LeagueSettings) -> str:
    value = (settings_row.waiver_type or "priority").strip().lower()
    if value in {"faab", "faab waivers", "faab_waivers"}:
        return "faab"
    return "priority"


def _slot_limits(settings_row: LeagueSettings) -> dict[str, int]:
    slots = settings_row.roster_slots_json or DEFAULT_ROSTER_SLOTS
    if not isinstance(slots, dict):
        return DEFAULT_ROSTER_SLOTS
    return {str(k): int(v) for k, v in slots.items()}


def _team_rows_for_league(db: Session, league_id: int) -> list[Team]:
    return (
        db.query(Team)
        .filter(Team.league_id == league_id)
        .order_by(Team.created_at.asc(), Team.id.asc())
        .all()
    )


def _ensure_team_waiver_state(db: Session, league_id: int) -> list[Team]:
    teams = _team_rows_for_league(db, league_id)
    if not teams:
        return []

    next_priority = 1
    for team in teams:
        if team.waiver_priority and team.waiver_priority > 0:
            continue
        team.waiver_priority = next_priority
        next_priority += 1
        db.add(team)

    sorted_by_priority = sorted(teams, key=lambda row: (int(row.waiver_priority or 0), row.id))
    for index, team in enumerate(sorted_by_priority, start=1):
        if team.waiver_priority != index:
            team.waiver_priority = index
            db.add(team)
        if team.faab_balance is None or team.faab_balance < 0:
            team.faab_balance = 100
            db.add(team)

    return sorted(sorted_by_priority, key=lambda row: (int(row.waiver_priority or 0), row.id))


def _team_name_map(db: Session, league_id: int) -> dict[int, str]:
    return {
        row.id: row.name
        for row in db.query(Team.id, Team.name).filter(Team.league_id == league_id).all()
    }


def _player_map(db: Session, player_ids: set[int]) -> dict[int, Player]:
    if not player_ids:
        return {}
    rows = db.query(Player).filter(Player.id.in_(player_ids)).all()
    return {row.id: row for row in rows}


def _record_transaction(
    db: Session,
    *,
    league_id: int,
    team_id: int,
    transaction_type: str,
    created_by_user_id: int | None,
    player_id: int | None = None,
    related_player_id: int | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        Transaction(
            league_id=league_id,
            team_id=team_id,
            transaction_type=transaction_type,
            player_id=player_id,
            related_player_id=related_player_id,
            created_by_user_id=created_by_user_id,
            reason=reason,
        )
    )


def _serialize_claim(
    claim: WaiverClaim,
    *,
    team_name_by_id: dict[int, str],
    player_by_id: dict[int, Player],
) -> WaiverClaimRead:
    add_player = player_by_id.get(claim.add_player_id)
    drop_player = player_by_id.get(claim.drop_player_id or -1)
    return WaiverClaimRead(
        id=claim.id,
        league_id=claim.league_id,
        team_id=claim.team_id,
        team_name=team_name_by_id.get(claim.team_id),
        add_player_id=claim.add_player_id,
        add_player_name=add_player.name if add_player else None,
        drop_player_id=claim.drop_player_id,
        drop_player_name=drop_player.name if drop_player else None,
        bid_amount=int(claim.bid_amount or 0),
        note=claim.note,
        priority_snapshot=claim.priority_snapshot,
        status=claim.status,
        process_batch_key=claim.process_batch_key,
        processed_reason=claim.processed_reason,
        processed_at=claim.processed_at,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


def _roster_rows_for_league(db: Session, league_id: int) -> list[RosterEntry]:
    return (
        db.query(RosterEntry)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league_id)
        .all()
    )


def _find_roster_entry(rows: list[RosterEntry], player_id: int) -> RosterEntry | None:
    for row in rows:
        if row.player_id == player_id:
            return row
    return None


def _resolve_best_slot(
    *,
    team_rows: list[RosterEntry],
    slot_limits: dict[str, int],
    player_position: str,
    drop_player_id: int | None,
) -> str | None:
    counts: dict[str, int] = {}
    for row in team_rows:
        if drop_player_id is not None and row.player_id == drop_player_id:
            continue
        counts[row.slot] = counts.get(row.slot, 0) + 1

    primary_limit = int(slot_limits.get(player_position, 0))
    if primary_limit > counts.get(player_position, 0):
        return player_position

    bench_limit = int(slot_limits.get("BENCH", 0))
    if bench_limit > counts.get("BENCH", 0):
        return "BENCH"

    return None


def _emit_waiver_event(db: Session, *, league_id: int, event_type: str, payload: dict) -> None:
    append_league_event(
        db,
        league_id=league_id,
        event_type=event_type,
        entity_type="waiver",
        payload=payload,
    )


@router.post("/leagues/{league_id}/waivers/claims", response_model=WaiverClaimRead, status_code=status.HTTP_201_CREATED)
def create_waiver_claim_endpoint(
    league_id: int,
    payload: WaiverClaimCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WaiverClaimRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)

    team = require_team_owner(db, payload.team_id, current_user)
    if team.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team does not belong to this league")
    idem_scope = f"league:{league.id}:waivers:claim:create"
    replay = get_completed_idempotent_response(
        db,
        scope=idem_scope,
        idempotency_key=idempotency_key,
    )
    if replay is not None:
        status_code, response_payload = replay
        return JSONResponse(status_code=status_code, content=response_payload)

    settings_row = _league_settings(db, league.id)
    waiver_mode = _waiver_mode(settings_row)
    slot_limits = _slot_limits(settings_row)

    add_player = db.get(Player, payload.add_player_id)
    if not add_player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player to add not found")

    already_rostered = (
        db.query(RosterEntry)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league.id, RosterEntry.player_id == add_player.id)
        .first()
    )
    if already_rostered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is already rostered in this league")

    duplicate_pending = (
        db.query(WaiverClaim)
        .filter(
            WaiverClaim.league_id == league.id,
            WaiverClaim.team_id == team.id,
            WaiverClaim.add_player_id == add_player.id,
            WaiverClaim.status.in_(list(PENDING_STATUSES)),
        )
        .first()
    )
    if duplicate_pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="team already has a pending claim for this player")

    team_roster_rows = (
        db.query(RosterEntry)
        .filter(RosterEntry.team_id == team.id)
        .all()
    )
    if any(row.player_id == add_player.id for row in team_roster_rows):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is already on your roster")

    drop_player_id = payload.drop_player_id
    if drop_player_id is not None and not any(row.player_id == drop_player_id for row in team_roster_rows):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="drop player is not on your roster")

    best_slot = _resolve_best_slot(
        team_rows=team_roster_rows,
        slot_limits=slot_limits,
        player_position=add_player.position,
        drop_player_id=drop_player_id,
    )
    if best_slot is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="roster is full for this move; include a valid drop player",
        )

    team_states = _ensure_team_waiver_state(db, league.id)
    team_by_id = {row.id: row for row in team_states}
    current_team = team_by_id.get(team.id)
    if not current_team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team waiver state unavailable")

    bid_amount = int(payload.bid_amount or 0)
    if bid_amount < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bid_amount must be >= 0")
    if waiver_mode == "faab" and bid_amount > int(current_team.faab_balance or 0):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="bid exceeds team FAAB balance")
    if waiver_mode != "faab":
        bid_amount = 0

    idem = begin_idempotent_request(
        db,
        scope=idem_scope,
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)

    claim = WaiverClaim(
        league_id=league.id,
        team_id=team.id,
        created_by_user_id=current_user.id,
        add_player_id=add_player.id,
        drop_player_id=drop_player_id,
        bid_amount=bid_amount,
        note=payload.note,
        priority_snapshot=current_team.waiver_priority,
        status="pending",
    )
    db.add(claim)
    db.flush()

    _emit_waiver_event(
        db,
        league_id=league.id,
        event_type="waiver.claim.created",
        payload={
            "claim_id": claim.id,
            "team_id": claim.team_id,
            "add_player_id": claim.add_player_id,
            "bid_amount": claim.bid_amount,
            "mode": waiver_mode,
        },
    )

    try:
        team_name_by_id = _team_name_map(db, league.id)
        player_ids = {claim.add_player_id}
        if claim.drop_player_id is not None:
            player_ids.add(claim.drop_player_id)
        player_by_id = _player_map(db, player_ids)
        response_payload = _serialize_claim(
            claim,
            team_name_by_id=team_name_by_id,
            player_by_id=player_by_id,
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


@router.get("/leagues/{league_id}/waivers/claims", response_model=WaiverClaimList)
def list_waiver_claims_endpoint(
    league_id: int,
    status_filter: str | None = None,
    team_id: int | None = None,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WaiverClaimList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)

    query = db.query(WaiverClaim).filter(WaiverClaim.league_id == league.id)
    if status_filter:
        query = query.filter(WaiverClaim.status == status_filter.strip().lower())
    if team_id is not None:
        query = query.filter(WaiverClaim.team_id == team_id)

    total = query.count()
    rows = (
        query.order_by(WaiverClaim.created_at.desc(), WaiverClaim.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 200)))
        .all()
    )

    team_name_by_id = _team_name_map(db, league.id)
    player_ids: set[int] = set()
    for row in rows:
        player_ids.add(row.add_player_id)
        if row.drop_player_id is not None:
            player_ids.add(row.drop_player_id)
    player_by_id = _player_map(db, player_ids)

    return WaiverClaimList(
        data=[_serialize_claim(row, team_name_by_id=team_name_by_id, player_by_id=player_by_id) for row in rows],
        total=total,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )


@router.post("/leagues/{league_id}/waivers/claims/{claim_id}/cancel", response_model=WaiverClaimRead)
def cancel_waiver_claim_endpoint(
    league_id: int,
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WaiverClaimRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)

    claim = db.get(WaiverClaim, claim_id)
    if not claim or claim.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="waiver claim not found")

    team = db.get(Team, claim.team_id)
    if not team or team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team ownership required")

    if claim.status not in PENDING_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="claim is no longer pending")

    claim.status = "cancelled"
    claim.processed_reason = "cancelled by owner"
    claim.processed_at = _utc_now()
    db.add(claim)

    _emit_waiver_event(
        db,
        league_id=league.id,
        event_type="waiver.claim.cancelled",
        payload={"claim_id": claim.id, "team_id": claim.team_id},
    )

    db.commit()
    db.refresh(claim)

    team_name_by_id = _team_name_map(db, league.id)
    player_ids = {claim.add_player_id}
    if claim.drop_player_id is not None:
        player_ids.add(claim.drop_player_id)
    player_by_id = _player_map(db, player_ids)
    return _serialize_claim(claim, team_name_by_id=team_name_by_id, player_by_id=player_by_id)


@router.post("/leagues/{league_id}/waivers/process", response_model=WaiverProcessResponse)
def process_waiver_claims_endpoint(
    league_id: int,
    payload: WaiverProcessRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WaiverProcessResponse:
    league, _membership = require_commissioner(db, league_id, current_user)
    idem = begin_idempotent_request(
        db,
        scope=f"league:{league.id}:waivers:process",
        idempotency_key=idempotency_key,
        created_by_user_id=current_user.id,
    )
    if idem.replay and idem.response_payload is not None and idem.response_status_code is not None:
        return JSONResponse(status_code=idem.response_status_code, content=idem.response_payload)
    batch_key = payload.batch_key.strip() if payload.batch_key else f"{league.season_year}-w1-{int(_utc_now().timestamp())}"
    try:
        execution = process_pending_waiver_claims(
            db,
            league_id=league.id,
            acted_by_user_id=current_user.id,
            batch_key=batch_key,
        )
        append_admin_action(
            db,
            league_id=league.id,
            actor_user_id=current_user.id,
            action_type="waivers.processed",
            target_type="league",
            target_id=league.id,
            metadata={
                "batch_key": batch_key,
                "processed_count": execution.response.processed_count,
                "won_count": execution.response.won_count,
                "lost_count": execution.response.lost_count,
                "invalid_count": execution.response.invalid_count,
            },
        )
        response_payload = execution.response.model_dump(mode="json")
        complete_idempotent_request(
            db,
            start=idem,
            response_status_code=status.HTTP_200_OK,
            response_payload=response_payload,
        )
        db.commit()
        return response_payload
    except Exception:
        fail_idempotent_request(db, start=idem)
        db.commit()
        raise
