from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


def list_projections(
    db: Session,
    season: int,
    week: int,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[WeeklyProjection], int]:
    query = select(WeeklyProjection).where(
        WeeklyProjection.season == season,
        WeeklyProjection.week == week,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(WeeklyProjection.fantasy_points.desc()).limit(limit).offset(offset)).all()
    return rows, total


def get_projection(
    db: Session, player_id: int, season: int, week: int
) -> WeeklyProjection | None:
    return db.scalar(
        select(WeeklyProjection).where(
            WeeklyProjection.player_id == player_id,
            WeeklyProjection.season == season,
            WeeklyProjection.week == week,
        )
    )
