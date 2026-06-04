#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app.db.session import SessionLocal
from api.app.models import load_model_registry
from api.app.services.player_import import (
    GOOGLE_SHEET_CSV_URL,
    import_players_from_csv_rows,
    read_csv_rows_from_path,
    read_csv_rows_from_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import draftable CFB players from Google Sheet CSV or local CSV.")
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--url", default=None, help="Google Sheet CSV export URL.")
    source.add_argument("--csv", default=None, help="Local CSV path.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and upsert without committing changes.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum CSV rows to process.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_label = args.csv or args.url or GOOGLE_SHEET_CSV_URL
    try:
        if args.csv:
            rows, headers = read_csv_rows_from_path(args.csv)
        else:
            rows, headers = read_csv_rows_from_url(args.url or GOOGLE_SHEET_CSV_URL)
    except Exception as exc:
        print(f"Failed to read player CSV: {exc}", file=sys.stderr)
        print("If Google Sheets is not public, export it as CSV and rerun with --csv ./data/players.csv.", file=sys.stderr)
        return 1

    load_model_registry()
    db = SessionLocal()
    try:
        result = import_players_from_csv_rows(
            db,
            rows,
            headers,
            source=source_label,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    except Exception as exc:
        db.rollback()
        print(f"Player import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(
        "Player import complete: "
        f"received={result.received} created={result.created} updated={result.updated} "
        f"skipped={result.skipped} failed={result.failed} dry_run={args.dry_run}"
    )
    for issue in result.issues[:25]:
        print(f"Skipped row {issue.row_number}: {issue.reason}")
    if len(result.issues) > 25:
        print(f"... {len(result.issues) - 25} more skipped rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
