from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup


def calendar_cfb_week(season_year: int, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    season_start = datetime(season_year, 8, 24, tzinfo=timezone.utc)
    if now < season_start:
        return 1
    elapsed_days = (now - season_start).days
    return max(1, min((elapsed_days // 7) + 1, 15))


def resolve_current_week(
    db: Session,
    league: League,
    selected_week: int | None = None,
) -> int:
    if selected_week is not None and selected_week > 0:
        return selected_week

    live_week = (
        db.query(func.min(Matchup.week))
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.status.in_(("live", "in_progress")),
        )
        .scalar()
    )
    if live_week is not None:
        return int(live_week)

    scheduled_week = (
        db.query(func.min(Matchup.week))
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.status.in_(("scheduled", "projected")),
        )
        .scalar()
    )
    if scheduled_week is not None:
        return int(scheduled_week)

    return calendar_cfb_week(league.season_year)
