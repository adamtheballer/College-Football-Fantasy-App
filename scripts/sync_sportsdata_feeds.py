import argparse
import os
import sys
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.provider_cache import ensure_feed_fresh
from collegefootballfantasy_api.app.services.power4 import CANONICAL_POWER4_TEAMS
from collegefootballfantasy_api.app.services.sportsdata_sync import (
    sync_power4_injuries,
    sync_power4_players_from_sportsdata,
    sync_power4_schedule_from_sportsdata,
    sync_power4_standings_from_sportsdata,
)


def _sync_players(session, force_refresh: bool) -> None:
    refreshed, _ = ensure_feed_fresh(
        session,
        provider="sportsdata",
        feed="players_reference",
        scope={},
        refresh_fn=lambda: sync_power4_players_from_sportsdata(session),
        ttl_days=settings.sportsdata_reference_ttl_days,
        force_refresh=force_refresh,
    )
    session.commit()
    print(f"players_reference synced (refreshed={refreshed})")


def _sync_schedule(session, season: int, force_refresh: bool) -> None:
    refreshed, _ = ensure_feed_fresh(
        session,
        provider="sportsdata",
        feed="schedule_season",
        scope={"season": season},
        refresh_fn=lambda: sync_power4_schedule_from_sportsdata(session, season=season),
        ttl_days=settings.sportsdata_schedule_ttl_days,
        force_refresh=force_refresh,
    )
    session.commit()
    print(f"schedule_season synced for {season} (refreshed={refreshed})")


def _sync_standings(session, season: int, conference: str, force_refresh: bool) -> None:
    conferences = [conference] if conference != "ALL" else list(CANONICAL_POWER4_TEAMS.keys())
    for conference_key in conferences:
        refreshed, _ = ensure_feed_fresh(
            session,
            provider="sportsdata",
            feed="standings_conference",
            scope={"season": season, "conference": conference_key},
            refresh_fn=lambda ck=conference_key: sync_power4_standings_from_sportsdata(
                session,
                season=season,
                conference=ck,
            ),
            ttl_days=settings.sportsdata_standings_ttl_days,
            force_refresh=force_refresh,
        )
        session.commit()
        print(f"standings_conference synced for {conference_key} {season} (refreshed={refreshed})")


def _sync_injuries(session, season: int, week: int, conference: str, force_refresh: bool) -> None:
    conference_scope = None if conference == "ALL" else conference
    refreshed, _ = ensure_feed_fresh(
        session,
        provider="sportsdata",
        feed="injuries_week",
        scope={"season": season, "week": week},
        refresh_fn=lambda: sync_power4_injuries(
            session,
            season=season,
            week=week,
            conference=conference_scope,
        ),
        ttl_days=settings.sportsdata_injury_ttl_days,
        force_refresh=force_refresh,
    )
    session.commit()
    conf_label = conference_scope or "ALL"
    print(f"injuries_week synced for {season} W{week} ({conf_label}) (refreshed={refreshed})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual SportsData + fallback sync runner.")
    parser.add_argument(
        "--feed",
        choices=("players", "schedule", "standings", "injuries", "all"),
        default="all",
    )
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument(
        "--conference",
        type=str,
        choices=("ALL", "SEC", "BIG10", "BIG12", "ACC"),
        default="ALL",
    )
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.feed in {"players", "all"}:
            _sync_players(session, args.force_refresh)
        if args.feed in {"schedule", "all"}:
            _sync_schedule(session, args.season, args.force_refresh)
        if args.feed in {"standings", "all"}:
            _sync_standings(session, args.season, args.conference, args.force_refresh)
        if args.feed in {"injuries", "all"}:
            _sync_injuries(session, args.season, args.week, args.conference, args.force_refresh)
    finally:
        session.close()


if __name__ == "__main__":
    main()
