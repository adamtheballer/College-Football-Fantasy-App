from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.app.api.deps import (
    get_current_user,
    require_league_member,
    require_team_member,
    require_team_owner,
)
from api.app.db.session import get_db
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
from api.app.schemas.transaction import TransactionList
from api.app.services import roster_service

router = APIRouter()


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
    return roster_service.add_roster_entry(db, team, entry_in, current_user)


@router.get("/teams/{team_id}/roster", response_model=RosterEntryList)
def list_roster_entries_endpoint(
    team_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RosterEntryList:
    team = require_team_member(db, team_id, current_user)
    return roster_service.list_roster_entries(db, team, limit, offset)


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
    roster_service.delete_roster_entry(db, team, roster_entry_id, current_user)


@router.patch("/teams/{team_id}/lineup", response_model=LineupUpdateResponse)
def update_lineup_endpoint(
    team_id: int,
    payload: LineupUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LineupUpdateResponse:
    team = require_team_owner(db, team_id, current_user)
    return roster_service.update_lineup(db, team, payload, current_user)


@router.post("/teams/{team_id}/add-drop", response_model=AddDropResponse, status_code=status.HTTP_201_CREATED)
def add_drop_endpoint(
    team_id: int,
    payload: AddDropRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AddDropResponse:
    team = require_team_owner(db, team_id, current_user)
    return roster_service.add_drop(db, team, payload, current_user)


@router.get("/leagues/{league_id}/transactions", response_model=TransactionList)
def list_transactions_endpoint(
    league_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionList:
    require_league_member(db, league_id, current_user)
    return roster_service.list_transactions(db, league_id, limit, offset)
