from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.app.models.league import League
from api.app.models.league_settings import LeagueSettings
from api.app.models.lineup import Lineup, LineupEntry
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.models.user import User
from api.app.schemas.lineup import LineupAssignment, LineupEntryRead, LineupRead
from api.app.services.roster_lock_service import enforce_players_unlocked_for_week


BENCH_SLOTS = {"BENCH", "BE", "IR"}


def canonical_slot(slot: str) -> str:
    normalized = (slot or "").strip().upper()
    if normalized.startswith("BENCH"):
        return "BENCH"
    if normalized.startswith("IR"):
        return "IR"
    while normalized and normalized[-1].isdigit():
        normalized = normalized[:-1]
    return normalized or "BENCH"


def is_starter_slot(slot: str) -> bool:
    return canonical_slot(slot) not in BENCH_SLOTS


def _settings_slots(db: Session, league_id: int) -> dict[str, int]:
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    raw = settings.roster_slots_json if settings and isinstance(settings.roster_slots_json, dict) else {}
    slots: dict[str, int] = {}
    for key, value in raw.items():
        try:
            slots[canonical_slot(str(key))] = int(value)
        except (TypeError, ValueError):
            continue
    return slots


def _roster_entries(db: Session, team: Team) -> list[tuple[RosterEntry, Player]]:
    return (
        db.query(RosterEntry, Player)
        .join(Player, Player.id == RosterEntry.player_id)
        .filter(RosterEntry.team_id == team.id, RosterEntry.league_id == team.league_id)
        .order_by(RosterEntry.id.asc())
        .all()
    )


def get_or_create_lineup(db: Session, league: League, team: Team, season: int, week: int) -> Lineup:
    if team.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team not found")
    lineup = (
        db.query(Lineup)
        .filter(
            Lineup.league_id == league.id,
            Lineup.team_id == team.id,
            Lineup.season == season,
            Lineup.week == week,
        )
        .first()
    )
    if lineup:
        return lineup

    lineup = Lineup(league_id=league.id, team_id=team.id, season=season, week=week, status="editable")
    db.add(lineup)
    db.flush()
    for roster_entry, _player in _roster_entries(db, team):
        db.add(
            LineupEntry(
                lineup_id=lineup.id,
                roster_entry_id=roster_entry.id,
                player_id=roster_entry.player_id,
                slot=roster_entry.slot,
                is_starter=is_starter_slot(roster_entry.slot),
            )
        )
    db.commit()
    db.refresh(lineup)
    return lineup


def get_lineup_read_model(db: Session, lineup: Lineup) -> LineupRead:
    rows = (
        db.query(LineupEntry, Player)
        .join(Player, Player.id == LineupEntry.player_id)
        .filter(LineupEntry.lineup_id == lineup.id)
        .order_by(LineupEntry.is_starter.desc(), LineupEntry.slot.asc(), LineupEntry.id.asc())
        .all()
    )
    return LineupRead(
        id=lineup.id,
        league_id=lineup.league_id,
        team_id=lineup.team_id,
        season=lineup.season,
        week=lineup.week,
        status=lineup.status,
        locked_at=lineup.locked_at,
        entries=[
            LineupEntryRead(
                id=entry.id,
                lineup_id=entry.lineup_id,
                roster_entry_id=entry.roster_entry_id,
                player_id=entry.player_id,
                player_name=player.name,
                player_position=player.position,
                player_school=player.school,
                slot=entry.slot,
                is_starter=bool(entry.is_starter),
            )
            for entry, player in rows
        ],
    )


def is_lineup_locked(lineup: Lineup) -> bool:
    return lineup.status in {"locked", "final"}


def validate_lineup_assignments(
    db: Session,
    league: League,
    team: Team,
    assignments: list[LineupAssignment],
) -> dict[int, RosterEntry]:
    player_ids = [row.player_id for row in assignments]
    if len(player_ids) != len(set(player_ids)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate player in lineup")

    roster_rows = db.query(RosterEntry).filter(RosterEntry.league_id == league.id, RosterEntry.team_id == team.id).all()
    roster_by_player = {row.player_id: row for row in roster_rows}
    for assignment in assignments:
        roster_entry = roster_by_player.get(assignment.player_id)
        if not roster_entry:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player not on team roster")
        if assignment.roster_entry_id is not None and assignment.roster_entry_id != roster_entry.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="roster entry does not match player")

    slot_limits = _settings_slots(db, league.id)
    if slot_limits:
        counts: dict[str, int] = {}
        for assignment in assignments:
            slot = canonical_slot(assignment.slot)
            counts[slot] = counts.get(slot, 0) + 1
        for slot, count in counts.items():
            limit = slot_limits.get(slot)
            if limit is not None and count > limit:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"lineup exceeds {slot} slots")
    return roster_by_player


def update_lineup(
    db: Session,
    league: League,
    team: Team,
    season: int,
    week: int,
    assignments: list[LineupAssignment],
    current_user: User,
) -> Lineup:
    if team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team ownership required")
    lineup = get_or_create_lineup(db, league, team, season, week)
    if is_lineup_locked(lineup):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="lineup locked")

    existing_entries = (
        db.query(LineupEntry)
        .filter(LineupEntry.lineup_id == lineup.id)
        .all()
    )
    existing_by_player_id = {entry.player_id: entry for entry in existing_entries}
    assignment_by_player_id = {assignment.player_id: assignment for assignment in assignments}
    changed_player_ids: set[int] = set()
    for existing in existing_entries:
        assignment = assignment_by_player_id.get(existing.player_id)
        if assignment is None:
            changed_player_ids.add(existing.player_id)
            continue
        if existing.slot != assignment.slot or bool(existing.is_starter) != bool(assignment.is_starter):
            changed_player_ids.add(existing.player_id)
    for assignment in assignments:
        if assignment.player_id not in existing_by_player_id:
            changed_player_ids.add(assignment.player_id)

    enforce_players_unlocked_for_week(
        db,
        league=league,
        player_ids=changed_player_ids,
        action_label="lineup change",
        season=season,
        week=week,
    )

    roster_by_player = validate_lineup_assignments(db, league, team, assignments)
    db.query(LineupEntry).filter(LineupEntry.lineup_id == lineup.id).delete(synchronize_session=False)
    db.flush()
    for assignment in assignments:
        db.add(
            LineupEntry(
                lineup_id=lineup.id,
                roster_entry_id=roster_by_player[assignment.player_id].id,
                player_id=assignment.player_id,
                slot=assignment.slot,
                is_starter=bool(assignment.is_starter),
            )
        )
    db.commit()
    db.refresh(lineup)
    return lineup


def lock_lineup(db: Session, lineup: Lineup) -> Lineup:
    if lineup.status != "final":
        lineup.status = "locked"
        lineup.locked_at = datetime.now(timezone.utc)
    db.add(lineup)
    db.commit()
    db.refresh(lineup)
    return lineup
