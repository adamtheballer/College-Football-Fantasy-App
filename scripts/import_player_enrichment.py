#!/usr/bin/env python3
"""Run one approved, staged player-enrichment import.

This command does not fetch a provider.  It accepts only a local CSV and is a
dry run by default.  ``--apply`` requires a readable, checksum-verified
logical-backup manifest and wraps the selected stage in one transaction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.player_enrichment_import import (
    IDENTITY_FIELDS,
    WEEKLY_NUMERIC_FIELDS,
    import_completed_weekly_stats,
    import_historical_totals,
    import_identities_and_bios,
    import_weekly_projections,
    read_csv_rows,
    read_verified_aliases,
    source_sha256,
    verify_logical_backup,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("identities", "historical", "weekly-projections", "completed-stats"), required=True)
    parser.add_argument("--input", type=Path, required=True, help="Approved local CSV export; never a provider URL.")
    parser.add_argument("--verified-aliases", type=Path, help="Reviewed alias CSV, required for non-exact mappings.")
    parser.add_argument("--apply", action="store_true", help="Write one stage transactionally after a reviewed dry run.")
    parser.add_argument("--logical-backup-manifest", type=Path, help="JSON manifest for a readable pre-import logical backup.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path outside source exports.")
    return parser.parse_args()


def required_columns(stage: str) -> set[str]:
    if stage == "identities":
        return IDENTITY_FIELDS
    if stage == "historical":
        return IDENTITY_FIELDS | {"season", "historical_team", "season_type"}
    if stage == "weekly-projections":
        return IDENTITY_FIELDS | {"season", "week", "projection_version", "opponent_team"} | WEEKLY_NUMERIC_FIELDS
    return IDENTITY_FIELDS | {"season", "week", "stats_json"}


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    if not source.is_file():
        raise SystemExit("Approved staged source file does not exist.")
    if args.apply and not args.logical_backup_manifest:
        raise SystemExit("--apply requires --logical-backup-manifest from a verified logical PostgreSQL backup.")
    backup = verify_logical_backup(args.logical_backup_manifest) if args.apply else None
    rows = read_csv_rows(source, required=required_columns(args.stage))
    aliases = read_verified_aliases(args.verified_aliases)
    ensure_models_registered()
    with SessionLocal() as db:
        try:
            if args.stage == "identities":
                report = import_identities_and_bios(db, rows, approved_aliases=aliases, apply=args.apply)
            elif args.stage == "historical":
                report = import_historical_totals(db, rows, approved_aliases=aliases, apply=args.apply, source_sha256=source_sha256(source))
            elif args.stage == "weekly-projections":
                report = import_weekly_projections(db, rows, approved_aliases=aliases, apply=args.apply)
            else:
                report = import_completed_weekly_stats(db, rows, approved_aliases=aliases, apply=args.apply)
            if report.has_unresolved_identity_conflicts:
                db.rollback()
                payload = {**report.as_dict(), "applied": False, "blocked": "unresolved identity review rows", "backup": backup}
                print(json.dumps(payload, indent=2, sort_keys=True))
                return 2
            if args.apply:
                db.commit()
            else:
                db.rollback()
            payload = {**report.as_dict(), "applied": args.apply, "source_sha256": source_sha256(source), "backup": backup}
        except Exception:
            db.rollback()
            raise
    output = json.dumps(payload, indent=2, sort_keys=True)
    print(output)
    if args.report:
        args.report.expanduser().resolve().write_text(output + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
