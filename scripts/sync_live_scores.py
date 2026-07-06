from __future__ import annotations

import argparse
import time

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.provider_stats_service import sync_provider_weekly_player_stats
from collegefootballfantasy_api.app.services.scoring_worker_service import RetryPolicy, run_scoring_worker_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync raw provider stats and recalculate live fantasy scores.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--league-id", type=int, default=None)
    parser.add_argument("--provider", choices=("sportsdata", "espn"), default="espn")
    parser.add_argument("--watch", action="store_true", help="Keep polling provider stats and recalculating scores.")
    parser.add_argument("--interval-seconds", type=int, default=90, help="Polling interval in seconds. Must be 1-90.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Provider sync attempts per run.")
    parser.add_argument("--backoff-seconds", type=float, default=2.0, help="Initial retry backoff in seconds.")
    parser.add_argument("--lock-ttl-seconds", type=int, default=300, help="Scoring job lock TTL in seconds.")
    parser.add_argument("--stale-run-seconds", type=int, default=900, help="Age before running scoring runs are marked stale.")
    parser.add_argument("--worker-id", type=str, default=None, help="Optional stable worker identifier.")
    args = parser.parse_args()
    if args.interval_seconds < 1 or args.interval_seconds > 90:
        raise SystemExit("--interval-seconds must be between 1 and 90.")
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be at least 1.")
    return args


def upsert_provider_player_stats(provider: str, season: int, week: int) -> dict[str, int]:
    with SessionLocal() as db:
        return sync_provider_weekly_player_stats(db, provider=provider, season=season, week=week)


def run_once(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        result = run_scoring_worker_once(
            db,
            provider=args.provider,
            season=args.season,
            week=args.week,
            league_id=args.league_id,
            sync_provider_stats=lambda: upsert_provider_player_stats(args.provider, args.season, args.week),
            retry_policy=RetryPolicy(max_attempts=args.max_attempts, initial_backoff_seconds=args.backoff_seconds),
            lock_ttl_seconds=args.lock_ttl_seconds,
            stale_run_seconds=args.stale_run_seconds,
            worker_id=args.worker_id,
        )
    print(
        f"provider={args.provider} status={result.status} lock_acquired={result.lock_acquired} "
        f"run_id={result.run_id} retry_count={result.retry_count} "
        f"players_scored={result.players_updated} teams_scored={result.teams_updated} "
        f"matchups_updated={result.matchups_updated} message={result.message or ''}"
    )


def main() -> None:
    args = parse_args()
    if not args.watch:
        run_once(args)
        return
    while True:
        started_at = time.monotonic()
        run_once(args)
        elapsed = time.monotonic() - started_at
        time.sleep(max(0, args.interval_seconds - elapsed))


if __name__ == "__main__":
    main()
