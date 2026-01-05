from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.roster import add_roster_entry, delete_roster_entry, list_roster_entries
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.schemas.roster import RosterEntryCreate, RosterEntryList, RosterEntryRead

router = APIRouter()


@router.post(
    "/teams/{team_id}/roster",
    response_model=RosterEntryRead,
    status_code=status.HTTP_201_CREATED,
)
def add_roster_entry_endpoint(
    team_id: int, entry_in: RosterEntryCreate, db: Session = Depends(get_db)
) -> RosterEntryRead:
    return add_roster_entry(db, team_id, entry_in)


@router.get("/teams/{team_id}/roster", response_model=RosterEntryList)
def list_roster_entries_endpoint(
    team_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> RosterEntryList:
    entries, total = list_roster_entries(db, team_id=team_id, limit=limit, offset=offset)
    return RosterEntryList(data=entries, total=total, limit=limit, offset=offset)


@router.delete(
    "/teams/{team_id}/roster/{roster_entry_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_roster_entry_endpoint(
    team_id: int, roster_entry_id: int, db: Session = Depends(get_db)
) -> None:
    entry = db.get(RosterEntry, roster_entry_id)
    if not entry or entry.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")
    delete_roster_entry(db, entry)
