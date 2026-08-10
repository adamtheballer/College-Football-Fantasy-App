#!/usr/bin/env python3
"""Import the authoritative 2026 Power Four team schedule sheet.

The command defaults to a dry run.  Use --apply only after reviewing the JSON
report, which lists every validation error and player-school schedule match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.registry import load_all_models
from collegefootballfantasy_api.app.services.team_schedule_import import (
    import_team_schedule_rows,
    parse_schedule_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import canonical 2026 team schedules for player Game Logs.")
    parser.add_argument("--source", required=True, help="Sealed local schedule CSV snapshot; live URLs are forbidden.")
    parser.add_argument("--sealed-manifest", type=Path, help="Sealed source manifest required for --apply.")
    parser.add_argument("--season", type=int, default=2026)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate and report only (default).")
    mode.add_argument("--apply", action="store_true", help="Persist valid schedule and game rows.")
    parser.add_argument("--report-path", type=Path, help="Write the machine-readable JSON report to this path.")
    return parser.parse_args()


def load_source(source: str) -> str:
    if source.startswith(("http://", "https://", "docs.google.com/", "drive.google.com/")):
        raise ValueError("Schedule imports require a sealed local CSV snapshot, never a mutable live URL.")
    source_path = Path(source).expanduser()
    if not source_path.is_file():
        raise ValueError("Schedule source must be an existing local CSV snapshot.")
    return source_path.read_text(encoding="utf-8-sig")


def require_sealed_schedule_manifest(manifest_path: Path | None, source: str) -> None:
    if manifest_path is None or not manifest_path.is_file():
        raise ValueError("--apply requires a sealed source manifest.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_hash = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    snapshots = manifest.get("snapshots", []) if isinstance(manifest, dict) else []
    required_workbooks = {"player_id_details", "team_rankings", "player_previous_stats", "annual_projections", "schedules", "cfb27_ratings"}
    if {item.get("workbook") for item in snapshots if isinstance(item, dict)} != required_workbooks:
        raise ValueError("The supplied manifest is not a complete sealed six-workbook batch.")
    if not any(
        item.get("workbook") == "schedules" and item.get("sha256") == source_hash
        for item in snapshots if isinstance(item, dict)
    ):
        raise ValueError("The schedule CSV hash is not present in the sealed schedules manifest.")


def main() -> int:
    args = parse_args()
    if args.apply:
        try:
            require_sealed_schedule_manifest(args.sealed_manifest, args.source)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
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
