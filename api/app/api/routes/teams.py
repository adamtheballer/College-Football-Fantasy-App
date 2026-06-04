from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.app.api.deps import get_current_user, get_league_or_404, require_league_member
from api.app.crud.team import list_teams
from api.app.db.session import get_db
from api.app.models.team import Team
from api.app.models.user import User
from api.app.schemas.team import TeamCreate, TeamList, TeamRead

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
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamList:
    get_league_or_404(db, league_id)
    require_league_member(db, league_id, current_user)
    teams, total = list_teams(db, league_id=league_id, limit=limit, offset=offset)
    return TeamList(data=teams, total=total, limit=limit, offset=offset)
