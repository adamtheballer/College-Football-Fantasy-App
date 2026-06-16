from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.app.models.league import League
from api.app.models.league_settings import LeagueSettings
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.models.transaction import Transaction
from api.app.models.user import User
from api.app.schemas.roster import (
    AddDropRequest,
    AddDropResponse,
    LineupUpdateRequest,
    LineupUpdateResponse,
    RosterEntryCreate,
    RosterEntryList,
    RosterEntryRead,
)
from api.app.schemas.transaction import TransactionList, TransactionRead
from api.app.services.admin_actions import append_admin_action
from api.app.services.roster_lock_service import enforce_players_unlocked_for_week, enforce_roster_window_open

DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BENCH": 4,
    "IR": 1,
}


def load_roster_entry_rows(db: Session, team_id: int) -> list[RosterEntry]:
    return (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.team_id == team_id)
        .order_by(RosterEntry.id.asc())
        .all()
    )


def serialize_roster(db: Session, team_id: int) -> list[RosterEntryRead]:
    return [RosterEntryRead.model_validate(entry) for entry in load_roster_entry_rows(db, team_id)]


def league_settings(db: Session, league_id: int) -> LeagueSettings:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return settings_row


def enforce_lineup_window(db: Session, league_id: int) -> League:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    enforce_roster_window_open(db, league)
    return league


def slot_limits(settings_row: LeagueSettings) -> dict[str, int]:
    return settings_row.roster_slots_json or DEFAULT_ROSTER_SLOTS


def validate_slot_counts(slot_limits: dict[str, int], slots: list[str]) -> None:
    counts: dict[str, int] = {}
    for slot in slots:
        if slot not in slot_limits:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid roster slot: {slot}")
        counts[slot] = counts.get(slot, 0) + 1

    for slot, count in counts.items():
        limit = int(slot_limits.get(slot, 0))
        if count > limit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"lineup exceeds {slot} slots")


def ensure_player_exists(db: Session, player_id: int) -> Player:
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return player


def ensure_player_available(db: Session, league_id: int, player_id: int) -> None:
    existing = (
        db.query(RosterEntry)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league_id, RosterEntry.player_id == player_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster")


def record_transaction(
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


def record_roster_audit(
    db: Session,
    *,
    league_id: int,
    actor_user_id: int,
    action_type: str,
    target_id: int | None,
    metadata: dict,
    target_type: str = "roster_entry",
) -> None:
    append_admin_action(
        db,
        league_id=league_id,
        actor_user_id=actor_user_id,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )


def best_available_slot(
    db: Session,
    team: Team,
    player_position: str,
    exclude_entry_id: int | None = None,
) -> str:
    settings_row = league_settings(db, team.league_id)
    limits = slot_limits(settings_row)
    roster_entries = load_roster_entry_rows(db, team.id)
    counts: dict[str, int] = {}
    for entry in roster_entries:
        if exclude_entry_id is not None and entry.id == exclude_entry_id:
            continue
        counts[entry.slot] = counts.get(entry.slot, 0) + 1

    primary_limit = int(limits.get(player_position, 0))
    if primary_limit and counts.get(player_position, 0) < primary_limit:
        return player_position

    bench_limit = int(limits.get("BENCH", 0))
    if counts.get("BENCH", 0) < bench_limit:
        return "BENCH"

    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="team roster is full")


def _raise_roster_conflict(exc: IntegrityError) -> None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster") from exc


def add_roster_entry(db: Session, team: Team, entry_in: RosterEntryCreate, current_user: User) -> RosterEntryRead:
    league = enforce_lineup_window(db, team.league_id)
    ensure_player_exists(db, entry_in.player_id)
    enforce_players_unlocked_for_week(
        db,
        league=league,
        player_ids={entry_in.player_id},
        action_label="roster add",
    )
    ensure_player_available(db, team.league_id, entry_in.player_id)

    settings_row = league_settings(db, team.league_id)
    limits = slot_limits(settings_row)
    slots = [entry.slot for entry in load_roster_entry_rows(db, team.id)] + [entry_in.slot]
    validate_slot_counts(limits, slots)

    entry = RosterEntry(
        league_id=team.league_id,
        team_id=team.id,
        player_id=entry_in.player_id,
        slot=entry_in.slot,
        status=entry_in.status,
    )
    db.add(entry)
    try:
        record_transaction(
            db,
            league_id=team.league_id,
            team_id=team.id,
            transaction_type="add",
            created_by_user_id=current_user.id,
            player_id=entry.player_id,
        )
        record_roster_audit(
            db,
            league_id=team.league_id,
            actor_user_id=current_user.id,
            action_type="roster.added",
            target_id=entry.id,
            metadata={"team_id": team.id, "player_id": entry.player_id, "slot": entry.slot},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _raise_roster_conflict(exc)
    db.refresh(entry)
    refreshed = (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.id == entry.id)
        .one()
    )
    return RosterEntryRead.model_validate(refreshed)


def list_roster_entries(db: Session, team: Team, limit: int, offset: int) -> RosterEntryList:
    entries = serialize_roster(db, team.id)
    paged = entries[offset : offset + limit]
    return RosterEntryList(data=paged, total=len(entries), limit=limit, offset=offset)


def delete_roster_entry(db: Session, team: Team, roster_entry_id: int, current_user: User) -> None:
    league = enforce_lineup_window(db, team.league_id)
    entry = db.get(RosterEntry, roster_entry_id)
    if not entry or entry.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")

    dropped_player_id = entry.player_id
    enforce_players_unlocked_for_week(
        db,
        league=league,
        player_ids={dropped_player_id},
        action_label="roster drop",
    )
    db.delete(entry)
    try:
        record_transaction(
            db,
            league_id=team.league_id,
            team_id=team.id,
            transaction_type="drop",
            created_by_user_id=current_user.id,
            player_id=dropped_player_id,
        )
        record_roster_audit(
            db,
            league_id=team.league_id,
            actor_user_id=current_user.id,
            action_type="roster.dropped",
            target_id=roster_entry_id,
            metadata={"team_id": team.id, "player_id": dropped_player_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _raise_roster_conflict(exc)


def update_lineup(db: Session, team: Team, payload: LineupUpdateRequest, current_user: User) -> LineupUpdateResponse:
    league = enforce_lineup_window(db, team.league_id)
    settings_row = league_settings(db, team.league_id)
    limits = slot_limits(settings_row)
    roster_entries = load_roster_entry_rows(db, team.id)
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

    validate_slot_counts(limits, desired_slots)
    enforce_players_unlocked_for_week(
        db,
        league=league,
        player_ids={entry.player_id for entry, _previous_slot in changed_entries},
        action_label="lineup change",
    )

    for assignment in payload.assignments:
        roster_by_id[assignment.roster_entry_id].slot = assignment.slot

    for entry, previous_slot in changed_entries:
        record_transaction(
            db,
            league_id=team.league_id,
            team_id=team.id,
            transaction_type="lineup",
            created_by_user_id=current_user.id,
            player_id=entry.player_id,
            reason=f"{previous_slot} -> {entry.slot}",
        )
    if changed_entries:
        record_roster_audit(
            db,
            league_id=team.league_id,
            actor_user_id=current_user.id,
            action_type="roster.lineup_changed",
            target_type="team",
            target_id=team.id,
            metadata={
                "team_id": team.id,
                "changes": [
                    {"roster_entry_id": entry.id, "player_id": entry.player_id, "from": previous_slot, "to": entry.slot}
                    for entry, previous_slot in changed_entries
                ],
            },
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _raise_roster_conflict(exc)
    return LineupUpdateResponse(data=serialize_roster(db, team.id))


def add_drop(db: Session, team: Team, payload: AddDropRequest, current_user: User) -> AddDropResponse:
    league = enforce_lineup_window(db, team.league_id)
    add_player = ensure_player_exists(db, payload.add_player_id)
    ensure_player_available(db, team.league_id, add_player.id)

    drop_entry = db.get(RosterEntry, payload.drop_roster_entry_id)
    if not drop_entry or drop_entry.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")

    enforce_players_unlocked_for_week(
        db,
        league=league,
        player_ids={add_player.id, drop_entry.player_id},
        action_label="add/drop",
    )

    new_slot = best_available_slot(db, team, add_player.position, exclude_entry_id=drop_entry.id)
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
    try:
        transaction = record_transaction(
            db,
            league_id=team.league_id,
            team_id=team.id,
            transaction_type="add_drop",
            created_by_user_id=current_user.id,
            player_id=add_player.id,
            related_player_id=dropped_player_id,
            reason=payload.reason,
        )
        record_roster_audit(
            db,
            league_id=team.league_id,
            actor_user_id=current_user.id,
            action_type="roster.add_drop",
            target_type="team",
            target_id=team.id,
            metadata={
                "team_id": team.id,
                "added_player_id": add_player.id,
                "dropped_player_id": dropped_player_id,
                "slot": new_slot,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _raise_roster_conflict(exc)

    return AddDropResponse(
        roster=serialize_roster(db, team.id),
        transaction=TransactionRead.model_validate(transaction),
    )


def list_transactions(db: Session, league_id: int, limit: int, offset: int) -> TransactionList:
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
