#!/usr/bin/env python3
"""Import the authoritative 2026 Power Four team schedule sheet.

The command defaults to a dry run.  Use --apply only after reviewing the JSON
report, which lists every validation error and player-school schedule match.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.registry import load_all_models
from collegefootballfantasy_api.app.services.team_schedule_import import (
    import_team_schedule_rows,
    parse_schedule_csv,
)


DEFAULT_SOURCE = "https://docs.google.com/spreadsheets/d/1JnoISIE2fr_l7ze5qtAe2DIN4nFlI3CaZMdvaNHEnZQ/export?format=csv&gid=1843438972"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import canonical 2026 team schedules for player Game Logs.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Google Sheet CSV export URL or a local CSV file path.")
    parser.add_argument("--season", type=int, default=2026)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate and report only (default).")
    mode.add_argument("--apply", action="store_true", help="Persist valid schedule and game rows.")
    parser.add_argument("--report-path", type=Path, help="Write the machine-readable JSON report to this path.")
    return parser.parse_args()


def load_source(source: str) -> str:
    source_path = Path(source).expanduser()
    if source_path.exists():
        return source_path.read_text(encoding="utf-8")
    request = Request(source, headers={"User-Agent": "CollegeFootballFantasyScheduleImporter/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def main() -> int:
    args = parse_args()
    load_all_models()
    csv_text = load_source(args.source)
    rows, report = parse_schedule_csv(csv_text, season=args.season)
    try:
        with SessionLocal() as db:
            report = import_team_schedule_rows(db, rows, report, apply=args.apply)
            if not args.apply:
                db.rollback()
    except RuntimeError as exc:
        raise SystemExit(f"Schedule import failed: {exc}") from exc
    payload = report.to_dict()
    output = json.dumps(payload, indent=2, default=str, sort_keys=True)
    print(output)
    if args.report_path:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(output + "\n", encoding="utf-8")
    return 1 if report.has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
