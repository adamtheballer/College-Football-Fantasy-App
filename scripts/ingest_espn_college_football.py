from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.services.espn_ingestion_service import TARGETS


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily ESPN college football ingestion job.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--date", type=str, default=date.today().isoformat())
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument("--targets", type=str, default=",".join(TARGETS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--watch", action="store_true", help="Refresh in a loop for live/stat windows.")
    parser.add_argument("--refresh-interval-seconds", type=int, default=420)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--temp-http-cache-dir", type=str, default=None)
    parser.add_argument("--disable-temp-http-cache", action="store_true")
    parser.add_argument("--rate-limit-seconds", type=float, default=2.0)
    parser.add_argument("--http-cache-ttl-minutes", type=int, default=20)
    parser.add_argument("--max-requests-per-run", type=int, default=250)
    parser.add_argument("--max-concurrent-requests", type=int, default=1)
    parser.add_argument("--cache-ttl-overrides-json", type=str, default=None)
    parser.add_argument("--output-location", type=str, default="data/espn_college_football")
    parser.add_argument(
        "--storage-url",
        type=str,
        default=None,
        help="Optional DATABASE_URL override for this process.",
    )
    args = parser.parse_args()
    if args.storage_url:
        os.environ["DATABASE_URL"] = args.storage_url
    if args.rate_limit_seconds < 0:
        raise SystemExit("--rate-limit-seconds must be non-negative")
    if args.max_requests_per_run < 1:
        raise SystemExit("--max-requests-per-run must be at least 1")
    if args.max_concurrent_requests != 1:
        raise SystemExit("--max-concurrent-requests must be 1; this job intentionally runs serial ESPN requests")
    if args.http_cache_ttl_minutes < 10 or args.http_cache_ttl_minutes > 30:
        raise SystemExit("--http-cache-ttl-minutes must be between 10 and 30")
    if args.refresh_interval_seconds < 60:
        raise SystemExit("--refresh-interval-seconds must be at least 60")
    return args


def run_once(args: argparse.Namespace) -> dict:
    from collegefootballfantasy_api.app.db.session import SessionLocal
    from collegefootballfantasy_api.app.services.espn_ingestion_service import (
        CachedESPNFetcher,
        ESPNCollegeFootballIngestion,
        TempHTTPResponseCache,
        live_stats_ttl_overrides,
        parse_ttl_overrides,
        validate_targets,
    )

    targets = validate_targets([target.strip() for target in args.targets.split(",") if target.strip()])
    run_date = _parse_date(args.date)
    ttl_overrides = parse_ttl_overrides(args.cache_ttl_overrides_json)
    if args.watch:
        watch_overrides = live_stats_ttl_overrides(args.refresh_interval_seconds)
        watch_overrides.update(ttl_overrides)
        ttl_overrides = watch_overrides

    output_dir = Path(args.output_location)
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_cache = None
    if not args.disable_temp_http_cache:
        temp_cache = TempHTTPResponseCache(
            args.temp_http_cache_dir,
            ttl_seconds=args.refresh_interval_seconds,
        )

    with SessionLocal() as db:
        fetcher = CachedESPNFetcher(
            db,
            rate_limit_seconds=args.rate_limit_seconds,
            max_requests_per_run=args.max_requests_per_run,
            cache_only=args.cache_only,
            force_refresh=args.force_refresh,
            write_cache=not args.dry_run,
            temp_cache=temp_cache,
        )
        service = ESPNCollegeFootballIngestion(
            db,
            fetcher=fetcher,
            http_cache_ttl_minutes=args.http_cache_ttl_minutes,
            ttl_overrides=ttl_overrides,
        )
        summary = service.run(
            season=args.season,
            run_date=run_date,
            week=args.week,
            targets=targets,
            dry_run=args.dry_run,
        )

    summary_payload = summary.as_dict()
    summary_path = output_dir / "latest_summary.json"
    summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary_payload, indent=2, sort_keys=True))
    return summary_payload


def main() -> None:
    args = parse_args()
    if not args.watch:
        summary_payload = run_once(args)
        if summary_payload["status"] == "failed":
            raise SystemExit(1)
        return

    while True:
        started_at = time.monotonic()
        summary_payload = run_once(args)
        if summary_payload["status"] == "failed":
            raise SystemExit(1)
        elapsed = time.monotonic() - started_at
        time.sleep(max(0, args.refresh_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
