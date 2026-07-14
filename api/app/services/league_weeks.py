from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup

CFB_WEEK_START_WEEKDAY = 3
CFB_WEEK_END_WEEKDAY = 6
TRADE_PROCESSING_WEEKDAYS = {0, 1, 2}
MAX_CFB_REGULAR_SEASON_WEEK = 15


@dataclass(frozen=True)
class CfbWeekState:
    season_year: int
    week: int
    week_starts_at: datetime
    week_ends_at: datetime
    trade_processing_opens_at: datetime
    game_week_active: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def season_week_one_start(season_year: int) -> datetime:
    anchor = datetime(season_year, 8, 24, tzinfo=timezone.utc)
    days_since_thursday = (anchor.weekday() - CFB_WEEK_START_WEEKDAY) % 7
    return anchor - timedelta(days=days_since_thursday)


def calendar_cfb_week(season_year: int, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    season_start = season_week_one_start(season_year)
    if now < season_start:
        return 1
    elapsed_days = (now - season_start).days
    return max(1, min((elapsed_days // 7) + 1, MAX_CFB_REGULAR_SEASON_WEEK))


def _next_monday_start(local_time: datetime) -> datetime:
    days_until_monday = (7 - local_time.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = local_time + timedelta(days=days_until_monday)
    return datetime.combine(next_monday.date(), time.min, tzinfo=local_time.tzinfo)


def is_cfb_game_week_active(now: datetime | None = None, timezone_name: str = "UTC") -> bool:
    league_tz = _timezone(timezone_name)
    local_time = _as_utc(now or datetime.now(timezone.utc)).astimezone(league_tz)
    return CFB_WEEK_START_WEEKDAY <= local_time.weekday() <= CFB_WEEK_END_WEEKDAY


def next_cfb_trade_process_time(accepted_at: datetime, timezone_name: str = "UTC") -> datetime:
    league_tz = _timezone(timezone_name)
    local_time = _as_utc(accepted_at).astimezone(league_tz)

    if is_cfb_game_week_active(local_time, timezone_name):
        return _next_monday_start(local_time).astimezone(timezone.utc)

    candidate = local_time
    while True:
        candidate = candidate + timedelta(days=1)
        if candidate.weekday() < 5:
            break

    if candidate.weekday() not in TRADE_PROCESSING_WEEKDAYS:
        candidate = _next_monday_start(candidate)

    return candidate.astimezone(timezone.utc)


def current_cfb_week_state(
    season_year: int,
    now: datetime | None = None,
    timezone_name: str = "UTC",
) -> CfbWeekState:
    league_tz = _timezone(timezone_name)
    current = _as_utc(now or datetime.now(timezone.utc)).astimezone(league_tz)
    week = calendar_cfb_week(season_year, current.astimezone(timezone.utc))
    week_start_date = season_week_one_start(season_year).date() + timedelta(days=(week - 1) * 7)
    week_starts_at = datetime.combine(week_start_date, time.min, tzinfo=league_tz)
    week_ends_at = datetime.combine(week_start_date + timedelta(days=3), time.max, tzinfo=league_tz)
    trade_processing_opens_at = datetime.combine(week_start_date + timedelta(days=4), time.min, tzinfo=league_tz)
    return CfbWeekState(
        season_year=season_year,
        week=week,
        week_starts_at=week_starts_at.astimezone(timezone.utc),
        week_ends_at=week_ends_at.astimezone(timezone.utc),
        trade_processing_opens_at=trade_processing_opens_at.astimezone(timezone.utc),
        game_week_active=is_cfb_game_week_active(current, timezone_name),
    )


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
