from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup

CFB_WEEK_START_WEEKDAY = 3
CFB_WEEK_END_WEEKDAY = 6
TRADE_PROCESSING_WEEKDAYS = {0, 1, 2}
MAX_CFB_REGULAR_SEASON_WEEK = 15
FINAL_MATCHUP_STATUSES = {"final", "stat_corrected"}
MATCHUP_RESULTS_HOLD = timedelta(hours=24)


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


def _league_timezone_name(db: Session, league: League) -> str:
    """Use the league's draft timezone, falling back to the CFB schedule timezone."""
    draft = db.query(Draft).filter(Draft.league_id == league.id).first()
    return draft.timezone if draft and draft.timezone else "America/New_York"


def _matchup_rows_by_week(db: Session, league: League) -> dict[int, list[Matchup]]:
    rows = (
        db.query(Matchup)
        .filter(Matchup.league_id == league.id, Matchup.season == league.season_year)
        .order_by(Matchup.week.asc(), Matchup.id.asc())
        .all()
    )
    grouped: dict[int, list[Matchup]] = {}
    for matchup in rows:
        grouped.setdefault(int(matchup.week), []).append(matchup)
    return grouped


def _week_is_final(matchups: list[Matchup]) -> bool:
    return bool(matchups) and all((matchup.status or "").lower() in FINAL_MATCHUP_STATUSES for matchup in matchups)


def latest_fully_finalized_matchup_week(db: Session, league: League) -> int | None:
    """Return the last consecutive fully final scheduled week.

    Schedules imported midseason may start after Week 1. Missing weeks are not
    scheduled weeks, so they must not prevent a later complete week from
    finalizing; the first non-final scheduled week still blocks all later ones.
    """
    rows_by_week = _matchup_rows_by_week(db, league)
    completed_week: int | None = None
    for week in sorted(rows_by_week):
        if not _week_is_final(rows_by_week[week]):
            break
        completed_week = week
    return completed_week


def _rollover_at(matchups: list[Matchup], timezone_name: str) -> datetime:
    """Hold final results through Tuesday after the game weekend and for 24 hours.

    CFB's normal slate can finish on Sunday or Monday. A later correction must
    still remain visible for 24 hours, but it must not defer the next matchup
    all the way to the following Tuesday.
    """
    league_tz = _timezone(timezone_name)
    finalized_at = max(
        (_as_utc(matchup.updated_at or matchup.created_at) for matchup in matchups),
        default=datetime.now(timezone.utc),
    )
    local_finalized_at = finalized_at.astimezone(league_tz)
    minimum_hold_ends_at = finalized_at + MATCHUP_RESULTS_HOLD
    if local_finalized_at.weekday() > 1:
        return minimum_hold_ends_at

    days_until_tuesday = (1 - local_finalized_at.weekday()) % 7
    tuesday_start = datetime.combine(
        local_finalized_at.date() + timedelta(days=days_until_tuesday),
        time.min,
        tzinfo=league_tz,
    ).astimezone(timezone.utc)
    return max(minimum_hold_ends_at, tuesday_start)


def resolve_current_week(
    db: Session,
    league: League,
    selected_week: int | None = None,
    now: datetime | None = None,
) -> int:
    if selected_week is not None and selected_week > 0:
        return selected_week

    current = _as_utc(now or datetime.now(timezone.utc))
    rows_by_week = _matchup_rows_by_week(db, league)
    if not rows_by_week:
        return calendar_cfb_week(league.season_year, current)

    # Never advance past an unfinished week. A league can have multiple
    # matchups in a week, and all of them must be final before standings or
    # the default workspace are allowed to move ahead.
    completed_week = latest_fully_finalized_matchup_week(db, league)
    if completed_week is not None:
        completed_rows = rows_by_week[completed_week]
        if current < _rollover_at(completed_rows, _league_timezone_name(db, league)):
            return completed_week

        next_week = next((week for week in sorted(rows_by_week) if week > completed_week), None)
        if next_week is not None:
            return next_week

    calendar_week = calendar_cfb_week(league.season_year, current)
    for week in sorted(rows_by_week):
        if week <= calendar_week and not _week_is_final(rows_by_week[week]):
            return week

    # Before the first scheduled kickoff, or when an imported schedule is
    # ahead of the calendar, show the nearest available matchup rather than
    # incorrectly selecting the oldest projected row forever.
    return min(rows_by_week)
