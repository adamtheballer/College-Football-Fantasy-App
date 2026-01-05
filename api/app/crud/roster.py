from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.schemas.roster import RosterEntryCreate


def add_roster_entry(db: Session, team_id: int, entry_in: RosterEntryCreate) -> RosterEntry:
    entry = RosterEntry(team_id=team_id, **entry_in.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return db.scalars(
        select(RosterEntry).options(joinedload(RosterEntry.player)).where(RosterEntry.id == entry.id)
    ).one()


def list_roster_entries(db: Session, team_id: int, limit: int, offset: int) -> tuple[list[RosterEntry], int]:
    stmt = (
        select(RosterEntry)
        .where(RosterEntry.team_id == team_id)
        .options(joinedload(RosterEntry.player))
    )
    total = db.scalar(select(func.count()).select_from(RosterEntry).where(RosterEntry.team_id == team_id))
    entries = db.scalars(stmt.offset(offset).limit(limit)).all()
    return entries, total or 0


def delete_roster_entry(db: Session, entry: RosterEntry) -> None:
    db.delete(entry)
    db.commit()
