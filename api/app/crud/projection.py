from collections.abc import Collection

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


def _published_projection_priority():
    """Order versioned snapshots by the public projection they supersede.

    Projection rows are intentionally versioned for auditability.  They are
    *not* interchangeable API results, though: an operator correction must
    outrank the earlier preseason snapshot even when that snapshot was
    imported more recently.  Keeping this rule here gives all read paths one
    deterministic source of truth while retaining every historical row.
    """

    return case(
        (WeeklyProjection.projection_version == "LOCKED", 700),
        (WeeklyProjection.projection_version.like("CORRECTED%"), 600),
        (WeeklyProjection.projection_version == "FINAL", 500),
        (WeeklyProjection.projection_version == "MIDWEEK", 400),
        (WeeklyProjection.projection_version == "PRELIMINARY", 300),
        (WeeklyProjection.projection_version == "PRESEASON", 200),
        else_=100,
    )


def current_published_projections_query(
    *,
    season: int,
    week: int,
    player_ids: Collection[int] | None = None,
):
    """Return exactly one authoritative published projection per player.

    The database's uniqueness constraint includes ``projection_version`` so
    multiple audit snapshots can legitimately exist for a player and week.
    Use a ranked subquery instead of relying on database iteration order;
    otherwise duplicate rows can cause inflated or missing UI projections.
    """

    ranked_query = select(
        WeeklyProjection.id.label("projection_id"),
        func.row_number()
        .over(
            partition_by=WeeklyProjection.player_id,
            order_by=(
                _published_projection_priority().desc(),
                WeeklyProjection.updated_at.desc(),
                WeeklyProjection.id.desc(),
            ),
        )
        .label("projection_rank"),
    ).where(
        WeeklyProjection.season == season,
        WeeklyProjection.week == week,
        WeeklyProjection.is_published.is_(True),
    )
    if player_ids is not None:
        ranked_query = ranked_query.where(WeeklyProjection.player_id.in_(player_ids))

    ranked = ranked_query.subquery()
    return (
        select(WeeklyProjection)
        .join(ranked, WeeklyProjection.id == ranked.c.projection_id)
        .where(ranked.c.projection_rank == 1)
    )


def list_projections(
    db: Session,
    season: int,
    week: int,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[WeeklyProjection], int]:
    query = current_published_projections_query(season=season, week=week)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(WeeklyProjection.fantasy_points.desc()).limit(limit).offset(offset)).all()
    return rows, total


def get_projection(
    db: Session, player_id: int, season: int, week: int
) -> WeeklyProjection | None:
    return db.scalar(
        current_published_projections_query(
            season=season,
            week=week,
            player_ids=(player_id,),
        )
    )
