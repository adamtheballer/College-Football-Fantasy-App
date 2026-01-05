from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.league import get_league
from collegefootballfantasy_api.app.crud.team import create_team, list_teams
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.schemas.team import TeamCreate, TeamList, TeamRead

router = APIRouter()


@router.post(
    "/leagues/{league_id}/teams",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
)
def create_team_endpoint(
    league_id: int, team_in: TeamCreate, db: Session = Depends(get_db)
) -> TeamRead:
    league = get_league(db, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    return create_team(db, league_id, team_in)


@router.get("/leagues/{league_id}/teams", response_model=TeamList)
def list_teams_endpoint(
    league_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> TeamList:
    league = get_league(db, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    teams, total = list_teams(db, league_id=league_id, limit=limit, offset=offset)
    return TeamList(data=teams, total=total, limit=limit, offset=offset)
