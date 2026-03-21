from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, get_league_or_404, require_league_member
from collegefootballfantasy_api.app.crud.team import list_teams
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.team import TeamCreate, TeamList, TeamRead

router = APIRouter()


@router.post(
    "/leagues/{league_id}/teams",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
)
def create_team_endpoint(
    league_id: int,
    team_in: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamRead:
    get_league_or_404(db, league_id)
    require_league_member(db, league_id, current_user)

    existing_owner_team = (
        db.query(Team)
        .filter(Team.league_id == league_id, Team.owner_user_id == current_user.id)
        .first()
    )
    if existing_owner_team:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user already has a team in this league")

    existing_name = db.query(Team).filter(Team.league_id == league_id, Team.name == team_in.name).first()
    if existing_name:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="team name already exists in this league")

    team = Team(
        league_id=league_id,
        name=team_in.name,
        owner_name=current_user.first_name,
        owner_user_id=current_user.id,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return TeamRead.model_validate(team)


@router.get("/leagues/{league_id}/teams", response_model=TeamList)
def list_teams_endpoint(
    league_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamList:
    get_league_or_404(db, league_id)
    require_league_member(db, league_id, current_user)
    teams, total = list_teams(db, league_id=league_id, limit=limit, offset=offset)
    return TeamList(data=teams, total=total, limit=limit, offset=offset)
