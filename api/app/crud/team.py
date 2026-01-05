from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.schemas.team import TeamCreate


def create_team(db: Session, league_id: int, team_in: TeamCreate) -> Team:
    team = Team(league_id=league_id, **team_in.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def list_teams(db: Session, league_id: int, limit: int, offset: int) -> tuple[list[Team], int]:
    stmt = select(Team).where(Team.league_id == league_id)
    total = db.scalar(select(func.count()).select_from(Team).where(Team.league_id == league_id))
    teams = db.scalars(stmt.offset(offset).limit(limit)).all()
    return teams, total or 0
