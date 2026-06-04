import argparse
import os
import sys
import time
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from ingest_injuries import ingest_once


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run injury ingest repeatedly (default every 24 hours)."
    )
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument("--interval-hours", type=float, default=24.0)
    parser.add_argument("--once", action="store_true", help="Run once and exit.")
    parser.add_argument(
        "--emit-alerts",
        dest="emit_alerts",
        action="store_true",
        default=True,
        help="Emit INJURY notifications for new/changed rows (default: enabled).",
    )
    parser.add_argument(
        "--no-emit-alerts",
        dest="emit_alerts",
        action="store_false",
        help="Do not emit INJURY notifications.",
    )
    args = parser.parse_args()

    interval_seconds = max(300, int(args.interval_hours * 3600))
    run_count = 0

    while True:
        run_count += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            created, updated, removed, alerts = ingest_once(
                season=args.season,
                week=args.week,
                emit_alerts=args.emit_alerts,
            )
            print(
                f"[{now}] injury_sync run={run_count} season={args.season} week={args.week} "
                f"created={created} updated={updated} removed={removed} alerts={alerts}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[{now}] injury_sync run={run_count} failed: {exc}")
            if args.once:
                raise

        if args.once:
            break
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
