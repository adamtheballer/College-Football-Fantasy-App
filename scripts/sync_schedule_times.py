#!/usr/bin/env python3
"""Safely refresh canonical kickoff times for one fantasy week.

Dry-run by default.  Use ``--apply`` only after inspecting the summary:
    PYTHONPATH=. uv run python scripts/sync_schedule_times.py --season 2026 --week 2 --apply
"""

from __future__ import annotations

import argparse
import json

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.schedule_time_sync import resolve_schedule_sync_source, sync_schedule_times


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--source", choices=("auto", "espn", "sportsdata"), default="auto")
    parser.add_argument("--force-current-week", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Commit verified updates; otherwise roll back.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_models_registered()
    source = resolve_schedule_sync_source() if args.source == "auto" else args.source
    with SessionLocal() as db:
        try:
            summary = sync_schedule_times(
                db,
                season=args.season,
                week=args.week,
                source=source,
                force_current_week=args.force_current_week,
            )
            if args.apply and not summary.errors:
                db.commit()
            else:
                db.rollback()
            print(json.dumps({"applied": bool(args.apply and not summary.errors), **summary.as_dict()}, default=str, indent=2, sort_keys=True))
            return 0 if not summary.errors else 2
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    raise SystemExit(main())
