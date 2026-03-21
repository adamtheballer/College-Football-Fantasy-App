from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.schemas.league import LeagueCreate, LeagueUpdate


def create_league(db: Session, league_in: LeagueCreate) -> League:
    league = League(**league_in.model_dump())
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def list_leagues(
    db: Session,
    limit: int,
    offset: int,
    *,
    user_id: int | None = None,
    scope: str = "member",
) -> tuple[list[League], int]:
    stmt = select(League)

    if scope != "all" and user_id is not None:
        membership_subquery = select(LeagueMember.league_id).where(LeagueMember.user_id == user_id)
        if scope == "mine":
            stmt = stmt.where(League.commissioner_user_id == user_id)
        else:
            stmt = stmt.where(League.id.in_(membership_subquery))

    stmt = stmt.order_by(League.updated_at.desc(), League.id.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt)
    leagues = db.scalars(stmt.offset(offset).limit(limit)).all()
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
