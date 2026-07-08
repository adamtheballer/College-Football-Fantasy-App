from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.api.deps import (
    get_current_user,
    require_league_member,
    require_team_member,
    require_team_owner,
    require_verified_user,
)
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.domain.roster_rules import RosterRuleError, normalize_slot, validate_slot_for_position
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.lineup_change_event import LineupChangeEvent
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.roster import (
    AddDropRequest,
    AddDropResponse,
    LineupUpdateRequest,
    LineupUpdateResponse,
    RosterEntryCreate,
    RosterEntryList,
    RosterEntryRead,
)
from collegefootballfantasy_api.app.schemas.transaction import TransactionList, TransactionRead
from collegefootballfantasy_api.app.services.audit_service import record_audit_event
from collegefootballfantasy_api.app.services.roster_lock_service import (
    RosterLockError,
    active_scoring_week,
    ensure_player_unlocked,
    is_player_locked,
)
from collegefootballfantasy_api.app.services.watchlist_alerts import notify_watchlisted_player

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


def _load_roster_entry_rows(db: Session, team_id: int) -> list[RosterEntry]:
    return (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.team_id == team_id)
        .order_by(RosterEntry.id.asc())
        .all()
    )


def _load_roster_entry_rows_for_update(db: Session, team_id: int) -> list[RosterEntry]:
    return (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.team_id == team_id)
        .with_for_update()
        .order_by(RosterEntry.id.asc())
        .all()
    )


def _serialize_roster(db: Session, team_id: int) -> list[RosterEntryRead]:
    return [RosterEntryRead.model_validate(entry) for entry in _load_roster_entry_rows(db, team_id)]


def _league_settings(db: Session, league_id: int) -> LeagueSettings:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return settings_row


def _slot_limits(settings_row: LeagueSettings) -> dict[str, int]:
    return settings_row.roster_slots_json or DEFAULT_ROSTER_SLOTS


def _validate_slot_counts(slot_limits: dict[str, int], slots: list[str]) -> None:
    counts: dict[str, int] = {}
    for slot in slots:
        normalized_slot = normalize_slot(slot)
        if normalized_slot not in slot_limits:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid roster slot: {normalized_slot}")
        counts[normalized_slot] = counts.get(normalized_slot, 0) + 1

    for slot, count in counts.items():
        limit = int(slot_limits.get(slot, 0))
        if count > limit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"lineup exceeds {slot} slots")


def _ensure_player_exists(db: Session, player_id: int) -> Player:
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return player


def _ensure_unlocked_for_roster_change(db: Session, team: Team, player: Player) -> None:
    try:
        ensure_player_unlocked(db, team.league, player)
    except RosterLockError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _validate_slot_assignment(db: Session, team: Team, player: Player, slot: str) -> str:
    try:
        normalized_slot = normalize_slot(slot)
        validate_slot_for_position(normalized_slot, player.position)
    except RosterRuleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if normalized_slot == "IR" and not _is_ir_eligible(db, team.league.season_year, player.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is not IR eligible")
    return normalized_slot


def _is_ir_eligible(db: Session, season: int, player_id: int) -> bool:
    injury = (
        db.query(Injury)
        .filter(Injury.player_id == player_id, Injury.season == season)
        .order_by(Injury.week.desc(), Injury.id.desc())
        .first()
    )
    if not injury:
        return False
    return (injury.status or "").upper() not in {"", "FULL", "ACTIVE", "AVAILABLE"}


def _ensure_player_available(db: Session, league_id: int, player_id: int) -> None:
    existing = (
        db.query(RosterEntry)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league_id, RosterEntry.player_id == player_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster")


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
    idempotency_key: str | None = None,
) -> Transaction:
    row = Transaction(
        league_id=league_id,
        team_id=team_id,
        transaction_type=transaction_type,
        player_id=player_id,
        related_player_id=related_player_id,
        created_by_user_id=created_by_user_id,
        reason=reason,
        idempotency_key=idempotency_key,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def _record_lineup_change(
    db: Session,
    *,
    team: Team,
    player: Player,
    from_slot: str,
    to_slot: str,
    changed_by: int,
) -> None:
    week = active_scoring_week(db, team.league) or 1
    lock_state = "locked" if is_player_locked(db, team.league, player) else "unlocked"
    db.add(
        LineupChangeEvent(
            league_id=team.league_id,
            team_id=team.id,
            week=week,
            player_id=player.id,
            from_slot=from_slot,
            to_slot=to_slot,
            lock_state=lock_state,
            changed_by=changed_by,
        )
    )


def _notify_watchlist_roster_change(
    db: Session,
    *,
    league_id: int,
    player_id: int,
    player_name: str,
    team_name: str,
    alert_kind: str,
) -> None:
    if alert_kind == "ownership_change":
        title = f"{player_name} is now rostered"
        body = f"{player_name} was added by {team_name}."
    else:
        title = f"{player_name} is available"
        body = f"{player_name} was dropped and is available to watch."
    notify_watchlisted_player(
        db,
        player_id=player_id,
        league_id=league_id,
        alert_kind=alert_kind,
        title=title,
        body=body,
        payload={"team_name": team_name},
        source_entity_type="roster",
    )


def _best_available_slot(
    db: Session,
    team: Team,
    player_position: str,
    exclude_entry_id: int | None = None,
) -> str:
    settings_row = _league_settings(db, team.league_id)
    slot_limits = _slot_limits(settings_row)
    roster_entries = _load_roster_entry_rows(db, team.id)
    counts: dict[str, int] = {}
    for entry in roster_entries:
        if exclude_entry_id is not None and entry.id == exclude_entry_id:
            continue
        counts[normalize_slot(entry.slot)] = counts.get(normalize_slot(entry.slot), 0) + 1

    primary_limit = int(slot_limits.get(player_position, 0))
    if primary_limit and counts.get(player_position, 0) < primary_limit:
        return player_position

    bench_limit = int(slot_limits.get("BENCH", 0))
    if counts.get("BENCH", 0) < bench_limit:
        return "BENCH"

    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="team roster is full")


@router.post(
    "/teams/{team_id}/roster",
    response_model=RosterEntryRead,
    status_code=status.HTTP_201_CREATED,
)
def add_roster_entry_endpoint(
    team_id: int,
    entry_in: RosterEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> RosterEntryRead:
    team = require_team_owner(db, team_id, current_user)
    player = _ensure_player_exists(db, entry_in.player_id)
    _ensure_unlocked_for_roster_change(db, team, player)
    normalized_slot = _validate_slot_assignment(db, team, player, entry_in.slot)
    _ensure_player_available(db, team.league_id, entry_in.player_id)

    settings_row = _league_settings(db, team.league_id)
    slot_limits = _slot_limits(settings_row)
    slots = [entry.slot for entry in _load_roster_entry_rows_for_update(db, team.id)] + [normalized_slot]
    _validate_slot_counts(slot_limits, slots)

    entry = RosterEntry(
        league_id=team.league_id,
        team_id=team.id,
        player_id=entry_in.player_id,
        slot=normalized_slot,
        status=entry_in.status,
    )
    db.add(entry)
    _record_transaction(
        db,
        league_id=team.league_id,
        team_id=team.id,
        transaction_type="add",
        created_by_user_id=current_user.id,
        player_id=entry.player_id,
    )
    record_audit_event(
        db,
        action="roster.add",
        entity_type="roster_entry",
        entity_id=entry.id,
        league_id=team.league_id,
        team_id=team.id,
        actor_user_id=current_user.id,
        after={"player_id": entry.player_id, "slot": entry.slot, "status": entry.status},
    )
    _notify_watchlist_roster_change(
        db,
        league_id=team.league_id,
        player_id=entry.player_id,
        player_name=player.name,
        team_name=team.name,
        alert_kind="ownership_change",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster") from exc
    db.refresh(entry)
    refreshed = (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.id == entry.id)
        .one()
    )
    return RosterEntryRead.model_validate(refreshed)


@router.get("/teams/{team_id}/roster", response_model=RosterEntryList)
def list_roster_entries_endpoint(
    team_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RosterEntryList:
    team = require_team_member(db, team_id, current_user)
    entries = _serialize_roster(db, team.id)
    paged = entries[offset : offset + limit]
    return RosterEntryList(data=paged, total=len(entries), limit=limit, offset=offset)


@router.delete(
    "/teams/{team_id}/roster/{roster_entry_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_roster_entry_endpoint(
    team_id: int,
    roster_entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> None:
    team = require_team_owner(db, team_id, current_user)
    entry = db.get(RosterEntry, roster_entry_id)
    if not entry or entry.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")
    _ensure_unlocked_for_roster_change(db, team, entry.player)

    dropped_player_id = entry.player_id
    dropped_player_name = entry.player.name
    previous_slot = entry.slot
    db.delete(entry)
    _record_transaction(
        db,
        league_id=team.league_id,
        team_id=team.id,
        transaction_type="drop",
        created_by_user_id=current_user.id,
        player_id=dropped_player_id,
    )
    record_audit_event(
        db,
        action="roster.drop",
        entity_type="roster_entry",
        entity_id=entry.id,
        league_id=team.league_id,
        team_id=team.id,
        actor_user_id=current_user.id,
        before={"player_id": dropped_player_id, "slot": previous_slot},
    )
    _notify_watchlist_roster_change(
        db,
        league_id=team.league_id,
        player_id=dropped_player_id,
        player_name=dropped_player_name,
        team_name=team.name,
        alert_kind="available_after_waiver",
    )
    db.commit()


@router.patch("/teams/{team_id}/lineup", response_model=LineupUpdateResponse)
def update_lineup_endpoint(
    team_id: int,
    payload: LineupUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> LineupUpdateResponse:
    team = require_team_owner(db, team_id, current_user)
    settings_row = _league_settings(db, team.league_id)
    slot_limits = _slot_limits(settings_row)
    roster_entries = _load_roster_entry_rows(db, team.id)
    roster_by_id = {entry.id: entry for entry in roster_entries}

    requested_ids = [assignment.roster_entry_id for assignment in payload.assignments]
    if len(requested_ids) != len(set(requested_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="duplicate roster entry in lineup update")

    desired_slots = []
    changed_entries: list[tuple[RosterEntry, str]] = []
    for entry in roster_entries:
        assignment = next((item for item in payload.assignments if item.roster_entry_id == entry.id), None)
        next_slot = _validate_slot_assignment(db, team, entry.player, assignment.slot) if assignment else entry.slot
        desired_slots.append(next_slot)
        if assignment and assignment.slot != entry.slot:
            _ensure_unlocked_for_roster_change(db, team, entry.player)
            changed_entries.append((entry, entry.slot))

    if any(entry_id not in roster_by_id for entry_id in requested_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")

    _validate_slot_counts(slot_limits, desired_slots)

    for assignment in payload.assignments:
        entry = roster_by_id[assignment.roster_entry_id]
        entry.slot = _validate_slot_assignment(db, team, entry.player, assignment.slot)

    for entry, previous_slot in changed_entries:
        _record_lineup_change(
            db,
            team=team,
            player=entry.player,
            from_slot=previous_slot,
            to_slot=entry.slot,
            changed_by=current_user.id,
        )
        _record_transaction(
            db,
            league_id=team.league_id,
            team_id=team.id,
            transaction_type="lineup",
            created_by_user_id=current_user.id,
            player_id=entry.player_id,
            reason=f"{previous_slot} -> {entry.slot}",
        )
        record_audit_event(
            db,
            action="roster.lineup.move",
            entity_type="roster_entry",
            entity_id=entry.id,
            league_id=team.league_id,
            team_id=team.id,
            actor_user_id=current_user.id,
            before={"slot": previous_slot},
            after={"slot": entry.slot, "player_id": entry.player_id},
        )

    db.commit()
    return LineupUpdateResponse(data=_serialize_roster(db, team.id))


@router.post("/teams/{team_id}/add-drop", response_model=AddDropResponse, status_code=status.HTTP_201_CREATED)
def add_drop_endpoint(
    team_id: int,
    payload: AddDropRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> AddDropResponse:
    team = require_team_owner(db, team_id, current_user)
    idempotency_key = payload.idempotency_key.strip() if payload.idempotency_key else None
    if idempotency_key:
        existing_transaction = (
            db.query(Transaction)
            .filter(Transaction.team_id == team.id, Transaction.idempotency_key == idempotency_key)
            .first()
        )
        if existing_transaction:
            return AddDropResponse(
                roster=_serialize_roster(db, team.id),
                transaction=TransactionRead.model_validate(existing_transaction),
            )

    _load_roster_entry_rows_for_update(db, team.id)
    add_player = _ensure_player_exists(db, payload.add_player_id)
    _ensure_unlocked_for_roster_change(db, team, add_player)
    _ensure_player_available(db, team.league_id, add_player.id)

    drop_entry = db.get(RosterEntry, payload.drop_roster_entry_id)
    if not drop_entry or drop_entry.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")
    _ensure_unlocked_for_roster_change(db, team, drop_entry.player)

    new_slot = _best_available_slot(db, team, add_player.position, exclude_entry_id=drop_entry.id)
    new_slot = _validate_slot_assignment(db, team, add_player, new_slot)
    dropped_player_id = drop_entry.player_id
    dropped_player_name = drop_entry.player.name
    previous_slot = drop_entry.slot
    db.delete(drop_entry)
    db.flush()

    db.add(
        RosterEntry(
            league_id=team.league_id,
            team_id=team.id,
            player_id=add_player.id,
            slot=new_slot,
            status="active",
        )
    )
    transaction = _record_transaction(
        db,
        league_id=team.league_id,
        team_id=team.id,
        transaction_type="add_drop",
        created_by_user_id=current_user.id,
        player_id=add_player.id,
        related_player_id=dropped_player_id,
        reason=payload.reason,
        idempotency_key=idempotency_key,
    )
    record_audit_event(
        db,
        action="roster.add_drop",
        entity_type="transaction",
        entity_id=transaction.id,
        league_id=team.league_id,
        team_id=team.id,
        actor_user_id=current_user.id,
        before={"drop_player_id": dropped_player_id, "drop_slot": previous_slot},
        after={"add_player_id": add_player.id, "add_slot": new_slot, "idempotency_key": idempotency_key},
    )
    _notify_watchlist_roster_change(
        db,
        league_id=team.league_id,
        player_id=add_player.id,
        player_name=add_player.name,
        team_name=team.name,
        alert_kind="ownership_change",
    )
    _notify_watchlist_roster_change(
        db,
        league_id=team.league_id,
        player_id=dropped_player_id,
        player_name=dropped_player_name,
        team_name=team.name,
        alert_kind="available_after_waiver",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            existing_transaction = (
                db.query(Transaction)
                .filter(Transaction.team_id == team.id, Transaction.idempotency_key == idempotency_key)
                .first()
            )
            if existing_transaction:
                return AddDropResponse(
                    roster=_serialize_roster(db, team.id),
                    transaction=TransactionRead.model_validate(existing_transaction),
                )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="roster move conflict") from exc

    return AddDropResponse(
        roster=_serialize_roster(db, team.id),
        transaction=TransactionRead.model_validate(transaction),
    )


@router.get("/leagues/{league_id}/transactions", response_model=TransactionList)
def list_transactions_endpoint(
    league_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionList:
    require_league_member(db, league_id, current_user)
    rows = (
        db.query(Transaction)
        .filter(Transaction.league_id == league_id)
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    total = db.query(Transaction).filter(Transaction.league_id == league_id).count()
    return TransactionList(
        data=[TransactionRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
