from __future__ import annotations

import argparse
import time

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.waiver_service import process_waiver_claims


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process due fantasy waiver claims.")
    parser.add_argument("--league-id", type=int, default=None, help="Optional league scope.")
    parser.add_argument("--watch", action="store_true", help="Keep polling for due claims.")
    parser.add_argument("--interval-seconds", type=int, default=60, help="Polling interval. Must be 5-300 seconds.")
    args = parser.parse_args()
    if args.interval_seconds < 5 or args.interval_seconds > 300:
        raise SystemExit("--interval-seconds must be between 5 and 300.")
    return args


def run_once(league_id: int | None) -> None:
    with SessionLocal() as db:
        result = process_waiver_claims(db, league_id=league_id)
    scope = f"league_id={league_id}" if league_id is not None else "league_id=all"
    print(f"{scope} processed={result.processed} failed={result.failed} skipped={result.skipped}")


def main() -> None:
    args = parse_args()
    if not args.watch:
        run_once(args.league_id)
        return
    while True:
        started_at = time.monotonic()
        run_once(args.league_id)
        elapsed = time.monotonic() - started_at
        time.sleep(max(0, args.interval_seconds - elapsed))


if __name__ == "__main__":
    main()
