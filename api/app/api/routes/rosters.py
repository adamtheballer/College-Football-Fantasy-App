from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.api.deps import (
    get_current_user,
    require_league_member,
    require_team_member,
    require_team_owner,
)
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
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
        if slot not in slot_limits:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid roster slot: {slot}")
        counts[slot] = counts.get(slot, 0) + 1

    for slot, count in counts.items():
        limit = int(slot_limits.get(slot, 0))
        if count > limit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"lineup exceeds {slot} slots")


def _ensure_player_exists(db: Session, player_id: int) -> Player:
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return player


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
) -> Transaction:
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
    db.flush()
    db.refresh(row)
    return row


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
        counts[entry.slot] = counts.get(entry.slot, 0) + 1

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
    current_user: User = Depends(get_current_user),
) -> RosterEntryRead:
    team = require_team_owner(db, team_id, current_user)
    _ensure_player_exists(db, entry_in.player_id)
    _ensure_player_available(db, team.league_id, entry_in.player_id)

    settings_row = _league_settings(db, team.league_id)
    slot_limits = _slot_limits(settings_row)
    slots = [entry.slot for entry in _load_roster_entry_rows(db, team.id)] + [entry_in.slot]
    _validate_slot_counts(slot_limits, slots)

    entry = RosterEntry(
        league_id=team.league_id,
        team_id=team.id,
        player_id=entry_in.player_id,
        slot=entry_in.slot,
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
    db.commit()
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
    current_user: User = Depends(get_current_user),
) -> None:
    team = require_team_owner(db, team_id, current_user)
    entry = db.get(RosterEntry, roster_entry_id)
    if not entry or entry.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")

    dropped_player_id = entry.player_id
    db.delete(entry)
    _record_transaction(
        db,
        league_id=team.league_id,
        team_id=team.id,
        transaction_type="drop",
        created_by_user_id=current_user.id,
        player_id=dropped_player_id,
    )
    db.commit()


@router.patch("/teams/{team_id}/lineup", response_model=LineupUpdateResponse)
def update_lineup_endpoint(
    team_id: int,
    payload: LineupUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        next_slot = assignment.slot if assignment else entry.slot
        desired_slots.append(next_slot)
        if assignment and assignment.slot != entry.slot:
            changed_entries.append((entry, entry.slot))

    if any(entry_id not in roster_by_id for entry_id in requested_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")

    _validate_slot_counts(slot_limits, desired_slots)

    for assignment in payload.assignments:
        roster_by_id[assignment.roster_entry_id].slot = assignment.slot

    for entry, previous_slot in changed_entries:
        _record_transaction(
            db,
            league_id=team.league_id,
            team_id=team.id,
            transaction_type="lineup",
            created_by_user_id=current_user.id,
            player_id=entry.player_id,
            reason=f"{previous_slot} -> {entry.slot}",
        )

    db.commit()
    return LineupUpdateResponse(data=_serialize_roster(db, team.id))


@router.post("/teams/{team_id}/add-drop", response_model=AddDropResponse, status_code=status.HTTP_201_CREATED)
def add_drop_endpoint(
    team_id: int,
    payload: AddDropRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AddDropResponse:
    team = require_team_owner(db, team_id, current_user)
    add_player = _ensure_player_exists(db, payload.add_player_id)
    _ensure_player_available(db, team.league_id, add_player.id)

    drop_entry = db.get(RosterEntry, payload.drop_roster_entry_id)
    if not drop_entry or drop_entry.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")

    new_slot = _best_available_slot(db, team, add_player.position, exclude_entry_id=drop_entry.id)
    dropped_player_id = drop_entry.player_id
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
    )
    db.commit()

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
