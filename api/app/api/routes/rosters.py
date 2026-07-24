from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.api.deps import (
    get_current_user,
    require_league_member,
    require_team_member,
    require_team_owner,
    require_verified_user,
)
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.roster import (
    AddDropRequest,
    AddDropResponse,
    LineupUpdateRequest,
    LineupUpdateResponse,
    RosterEntryCreate,
    RosterEntryList,
    RosterEntryRead,
    RosterSlotRead,
)
from collegefootballfantasy_api.app.schemas.player import PlayerRead
from collegefootballfantasy_api.app.schemas.transaction import TransactionList, TransactionRead
from collegefootballfantasy_api.app.services.roster_legality import (
    eligible_slots_for_position,
    normalize_slot,
    superflex_is_enabled,
)
from collegefootballfantasy_api.app.services.roster_slots import (
    RosterSlotIntegrityError,
    build_team_roster_slots,
    first_open_eligible_slot,
)
from collegefootballfantasy_api.app.services.league_weeks import resolve_current_week
from collegefootballfantasy_api.app.services.player_lock_service import locked_player_ids

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


def _serialize_roster(db: Session, team: Team) -> list[RosterSlotRead]:
    settings_row = _league_settings(db, team.league_id)
    entries = _load_roster_entry_rows(db, team.id)
    try:
        slots = build_team_roster_slots(
            team.id,
            _slot_limits(settings_row),
            entries,
        )
    except RosterSlotIntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    league = db.get(League, team.league_id)
    player_ids = {entry.player_id for entry in entries}
    projections_by_player: dict[int, float] = {}
    if league and player_ids:
        week = resolve_current_week(db, league)
        projections_by_player = {
            row.player_id: float(row.fantasy_points or 0.0)
            for row in (
                db.query(WeeklyProjection)
                .filter(
                    WeeklyProjection.season == league.season_year,
                    WeeklyProjection.week == week,
                    WeeklyProjection.player_id.in_(player_ids),
                )
                .all()
            )
        }

    return [
        RosterSlotRead(
            slot_id=slot.slot_id,
            slot_type=slot.slot_type,
            slot_index=slot.slot_index,
            display_label=slot.display_label,
            is_starter=slot.is_starter,
            is_ir=slot.is_ir,
            id=slot.entry.id if slot.entry else None,
            team_id=team.id,
            league_id=team.league_id,
            player_id=slot.entry.player_id if slot.entry else None,
            slot=slot.slot_type,
            status=slot.entry.status if slot.entry else "EMPTY",
            player=PlayerRead.model_validate(slot.entry.player) if slot.entry and slot.entry.player else None,
            projection=projections_by_player.get(slot.entry.player_id, 0.0) if slot.entry else 0.0,
        )
        for slot in slots
    ]


def _league_settings(db: Session, league_id: int) -> LeagueSettings:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return settings_row


def _slot_limits(settings_row: LeagueSettings) -> dict[str, int]:
    raw_limits = settings_row.roster_slots_json or DEFAULT_ROSTER_SLOTS
    normalized_limits: dict[str, int] = {}
    for raw_slot, raw_count in raw_limits.items():
        slot = normalize_slot(raw_slot)
        if not slot:
            continue
        normalized_limits[slot] = int(raw_count or 0)
    return normalized_limits


def _validate_slot_counts(slot_limits: dict[str, int], slots: list[str]) -> None:
    counts: dict[str, int] = {}
    for slot in slots:
        normalized_slot = normalize_slot(slot)
        if normalized_slot is None or normalized_slot not in slot_limits:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid roster slot: {slot}")
        counts[normalized_slot] = counts.get(normalized_slot, 0) + 1

    for slot, count in counts.items():
        limit = int(slot_limits.get(slot, 0))
        if count > limit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"lineup exceeds {slot} slots")


def _validate_position_slot_eligibility(settings_row: LeagueSettings, player_position: str | None, slot: str) -> None:
    normalized_slot = normalize_slot(slot)
    if normalized_slot is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid roster slot: {slot}")
    if normalized_slot == "IR":
        return
    position = (player_position or "").upper()
    eligible_slots = eligible_slots_for_position(
        position,
        superflex_enabled=superflex_is_enabled(
            _slot_limits(settings_row),
            configured=bool(settings_row.superflex_enabled),
        ),
    )
    if normalized_slot not in eligible_slots:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{position or 'player'} is not eligible for {normalized_slot}",
        )


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
) -> tuple[str, int]:
    settings_row = _league_settings(db, team.league_id)
    slot_limits = _slot_limits(settings_row)
    roster_entries = _load_roster_entry_rows(db, team.id)
    if exclude_entry_id is not None:
        roster_entries = [entry for entry in roster_entries if entry.id != exclude_entry_id]
    slot = first_open_eligible_slot(
        team.id,
        player_position,
        slot_limits,
        roster_entries,
        superflex_enabled=superflex_is_enabled(
            slot_limits,
            configured=bool(settings_row.superflex_enabled),
        ),
    )
    if slot:
        return slot

    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Team roster is full.")


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
    _ensure_player_available(db, team.league_id, entry_in.player_id)

    settings_row = _league_settings(db, team.league_id)
    slot_limits = _slot_limits(settings_row)
    current_entries = _load_roster_entry_rows(db, team.id)
    _validate_position_slot_eligibility(settings_row, player.position, entry_in.slot)
    normalized_slot = normalize_slot(entry_in.slot)
    if normalized_slot is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid roster slot: {entry_in.slot}")
    try:
        canonical_slots = build_team_roster_slots(team.id, slot_limits, current_entries)
    except RosterSlotIntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    target_slot = next(
        (
            slot
            for slot in canonical_slots
            if slot.slot_type == normalized_slot
            and (entry_in.slot_index is None or slot.slot_index == entry_in.slot_index)
            and slot.entry is None
        ),
        None,
    )
    if target_slot is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"no open {normalized_slot} roster slot")

    entry = RosterEntry(
        league_id=team.league_id,
        team_id=team.id,
        player_id=entry_in.player_id,
        slot=normalized_slot,
        slot_index=target_slot.slot_index,
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
    slots = _serialize_roster(db, team)
    paged = slots[offset : offset + limit]
    return RosterEntryList(data=paged, slots=slots, total=len(slots), limit=limit, offset=offset)


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

    league = db.get(League, team.league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    if entry.player_id in locked_player_ids(
        db,
        player_ids={entry.player_id},
        season=league.season_year,
        week=resolve_current_week(db, league),
        now=datetime.now(timezone.utc),
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player cannot be dropped after kickoff")

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

    desired_slots: dict[int, tuple[str, int]] = {}
    changed_entries: list[tuple[RosterEntry, str, int]] = []
    assignments_by_entry_id = {assignment.roster_entry_id: assignment for assignment in payload.assignments}
    try:
        canonical_slots = build_team_roster_slots(team.id, slot_limits, roster_entries)
    except RosterSlotIntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    for entry in roster_entries:
        assignment = assignments_by_entry_id.get(entry.id)
        next_slot = normalize_slot(assignment.slot) if assignment else normalize_slot(entry.slot)
        if next_slot is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid roster slot")
        next_slot_index = assignment.slot_index if assignment and assignment.slot_index is not None else entry.slot_index
        if assignment and assignment.slot_index is None and next_slot != entry.slot:
            open_slot = next(
                (slot for slot in canonical_slots if slot.slot_type == next_slot and slot.entry is None),
                None,
            )
            if open_slot is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"no open {next_slot} roster slot")
            next_slot_index = open_slot.slot_index
        if next_slot_index is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="roster entry has no slot index")
        desired_slots[entry.id] = (next_slot, next_slot_index)
        if assignment and (next_slot != entry.slot or next_slot_index != entry.slot_index):
            _validate_position_slot_eligibility(
                settings_row,
                entry.player.position if entry.player else None,
                next_slot,
            )
            changed_entries.append((entry, entry.slot, entry.slot_index))

    if any(entry_id not in roster_by_id for entry_id in requested_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")

    target_keys = list(desired_slots.values())
    if len(target_keys) != len(set(target_keys)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="multiple players cannot occupy the same roster slot")

    if changed_entries:
        league = db.get(League, team.league_id)
        if not league:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
        locked_ids = locked_player_ids(
            db,
            player_ids={entry.player_id for entry, _, _ in changed_entries},
            season=league.season_year,
            week=resolve_current_week(db, league),
            now=datetime.now(timezone.utc),
        )
        if locked_ids:
            locked_names = sorted(
                entry.player.name
                for entry, _, _ in changed_entries
                if entry.player_id in locked_ids and entry.player is not None
            )
            detail = ", ".join(locked_names) or "the selected player"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"lineup changes are locked after kickoff for: {detail}",
            )

    for entry, _, _ in changed_entries:
        entry.slot_index = 100000 + entry.id
    if changed_entries:
        db.flush()
    for entry_id, (slot, slot_index) in desired_slots.items():
        roster_by_id[entry_id].slot = slot
        roster_by_id[entry_id].slot_index = slot_index

    for entry, previous_slot, previous_slot_index in changed_entries:
        _record_transaction(
            db,
            league_id=team.league_id,
            team_id=team.id,
            transaction_type="lineup",
            created_by_user_id=current_user.id,
            player_id=entry.player_id,
            reason=f"{previous_slot}{previous_slot_index} -> {entry.slot}{entry.slot_index}",
        )

    db.commit()
    return LineupUpdateResponse(
        data=[RosterEntryRead.model_validate(entry) for entry in _load_roster_entry_rows(db, team.id)]
    )


@router.post("/teams/{team_id}/add-drop", response_model=AddDropResponse, status_code=status.HTTP_201_CREATED)
def add_drop_endpoint(
    team_id: int,
    payload: AddDropRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> AddDropResponse:
    team = require_team_owner(db, team_id, current_user)
    add_player = _ensure_player_exists(db, payload.add_player_id)
    _ensure_player_available(db, team.league_id, add_player.id)

    drop_entry = db.get(RosterEntry, payload.drop_roster_entry_id)
    if not drop_entry or drop_entry.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")

    new_slot, new_slot_index = _best_available_slot(
        db,
        team,
        add_player.position,
        exclude_entry_id=drop_entry.id,
    )
    dropped_player_id = drop_entry.player_id
    db.delete(drop_entry)
    db.flush()

    db.add(
        RosterEntry(
            league_id=team.league_id,
            team_id=team.id,
            player_id=add_player.id,
            slot=new_slot,
            slot_index=new_slot_index,
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
        roster=_serialize_roster(db, team),
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
