import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.cfb27_player_sync import (
    load_reviewed_cfb27_snapshot,
    sync_cfb27_players,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync a reviewed CFB27 Sheets snapshot onto existing approved players.")
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Immutable CSV export created from the configured CFB27 Ratings Sheet (or a reviewed JSON fixture).",
    )
    parser.add_argument("--manifest", required=True, type=Path, help="Approved immutable manifest for --input.")
    parser.add_argument("--season", type=int, default=2026, help="Season whose Week 1 lifecycle gate must still be preseason.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without committing.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        ratings_path = args.input.expanduser().resolve()
        if not ratings_path.is_file():
            raise SystemExit(f"Reviewed CFB27 ratings snapshot does not exist: {ratings_path}")
        snapshot = load_reviewed_cfb27_snapshot(
            snapshot_path=ratings_path, manifest_path=args.manifest.expanduser().resolve()
        )
        result = sync_cfb27_players(session, snapshot=snapshot, dry_run=args.dry_run, season=args.season)
    finally:
        session.close()

    mode = "DRY RUN" if args.dry_run else "SYNCED"
    print(
        f"{mode}: dataset={snapshot.dataset_version} approved={snapshot.approval_status} "
        f"rows={snapshot.row_count} sha256={snapshot.sha256[:12]} {result}"
    )


if __name__ == "__main__":
    main()
