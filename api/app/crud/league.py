from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.schemas.league import LeagueCreate, LeagueUpdate


def create_league(db: Session, league_in: LeagueCreate) -> League:
    league = League(**league_in.model_dump())
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def list_leagues(db: Session, limit: int, offset: int) -> tuple[list[League], int]:
    total = db.scalar(select(func.count()).select_from(League))
    leagues = db.scalars(select(League).offset(offset).limit(limit)).all()
    return leagues, total or 0


def get_league(db: Session, league_id: int) -> League | None:
    return db.get(League, league_id)


def update_league(db: Session, league: League, league_in: LeagueUpdate) -> League:
    data = league_in.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(league, field, value)
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def delete_league(db: Session, league: League) -> None:
    db.delete(league)
    db.commit()
