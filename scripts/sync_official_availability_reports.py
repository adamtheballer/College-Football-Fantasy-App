"""Railway Cron entrypoint for official P4 availability-report refreshes."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
from collegefootballfantasy_api.app.services.provider_cache import ensure_feed_fresh
from collegefootballfantasy_api.app.services.sportsdata_sync import sync_power4_injuries


def should_run_at_local_hour(
    now_utc: datetime,
    *,
    timezone_name: str,
    hour: int | list[int] | None,
) -> bool:
    """Return whether a UTC cron invocation is inside a configured local hour."""
    if hour is None:
        return True
    hours = {hour} if isinstance(hour, int) else set(hour)
    return now_utc.astimezone(ZoneInfo(timezone_name)).hour in hours


def should_run_at_local_schedule(
    now_utc: datetime,
    *,
    timezone_name: str,
    hour: int | list[int] | None,
    weekday: int | list[int] | None,
) -> bool:
    """Return whether a cron invocation matches its local time and weekday.

    Railway evaluates cron expressions in UTC. Checking both values in the
    configured local timezone keeps a paired EST/EDT cron expression from
    running twice and prevents a manual or misconfigured invocation from
    refreshing availability reports on an unintended day.
    """

    local_time = now_utc.astimezone(ZoneInfo(timezone_name))
    if hour is not None:
        hours = {hour} if isinstance(hour, int) else set(hour)
        if local_time.hour not in hours:
            return False
    if weekday is not None:
        weekdays = {weekday} if isinstance(weekday, int) else set(weekday)
        if local_time.weekday() not in weekdays:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh official P4 availability reports once.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument(
        "--week",
        type=int,
        help="Override the game week. By default it is resolved from the CFB calendar.",
    )
    parser.add_argument(
        "--only-local-hour",
        type=int,
        choices=range(24),
        metavar="HOUR",
        action="append",
        help="Exit successfully unless the current time is this hour in --timezone.",
    )
    parser.add_argument(
        "--timezone",
        default="America/New_York",
        help="IANA timezone used with --only-local-hour (default: America/New_York).",
    )
    parser.add_argument(
        "--only-local-weekday",
        type=int,
        choices=range(7),
        metavar="WEEKDAY",
        action="append",
        help="Exit successfully unless this is a Python weekday in --timezone (Monday=0, Sunday=6).",
    )
    args = parser.parse_args()
    now_utc = datetime.now(timezone.utc)
    if not should_run_at_local_schedule(
        now_utc,
        timezone_name=args.timezone,
        hour=args.only_local_hour,
        weekday=args.only_local_weekday,
    ):
        print(
            "official availability reports skipped "
            f"utc={now_utc.isoformat()} timezone={args.timezone} "
            f"only_local_hour={args.only_local_hour} only_local_weekday={args.only_local_weekday}"
        )
        return

    week = args.week or calendar_cfb_week(args.season, now_utc)
    session = SessionLocal()
    try:
        refreshed, _state = ensure_feed_fresh(
            session,
            provider="official_conference_reports",
            feed="injuries_week",
            scope={"season": args.season, "week": week},
            refresh_fn=lambda: sync_power4_injuries(session, season=args.season, week=week),
            ttl_days=1,
            # A cron run must obtain the latest report even if the previous
            # run succeeded earlier that day. Manual callers can opt in too.
            force_refresh=True,
        )
        session.commit()
        print(f"official availability reports refreshed={refreshed} season={args.season} week={week}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
