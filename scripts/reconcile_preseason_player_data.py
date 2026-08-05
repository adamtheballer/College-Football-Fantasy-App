#!/usr/bin/env python3
"""Apply the reviewed preseason player universe in one database transaction.

This is the only release command allowed to mutate identity, projection,
eligibility, CFB27, and preseason-value state. Runtime startup verifies source
artifacts but never invokes this command.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.cfb27_player_sync import (
    load_reviewed_cfb27_snapshot,
    sync_cfb27_players,
)
from scripts.audit_preseason_source_contract import require_valid_source_directory
from scripts.bootstrap_canonical_player_data import (
    DEFAULT_IDENTITIES,
    DEFAULT_PROJECTIONS,
    ROOT_DIR,
    bootstrap,
)


DEFAULT_RATINGS = ROOT_DIR / "api" / "app" / "data" / "cfb27_ratings_2026-08-05.csv"
DEFAULT_RATINGS_MANIFEST = ROOT_DIR / "api" / "app" / "data" / "cfb27_ratings_2026-08-05.manifest.json"


def reconcile(*, identities: Path, projections: Path, ratings: Path, ratings_manifest: Path, season: int, dry_run: bool) -> dict[str, dict[str, int]]:
    """Reconcile every player-data source as one all-or-nothing release unit."""
    require_valid_source_directory(identities.parent)
    snapshot = load_reviewed_cfb27_snapshot(snapshot_path=ratings, manifest_path=ratings_manifest)
    with SessionLocal() as db:
        if dry_run:
            catalog = bootstrap(
                identities_path=identities,
                projections_path=projections,
                ratings_path=ratings,
                ratings_manifest_path=ratings_manifest,
                apply=False,
                db=db,
                commit=False,
            )
            ratings_result = sync_cfb27_players(db, snapshot=snapshot, dry_run=True, season=season, commit=False)
            return {"catalog": catalog, "ratings": ratings_result}

        try:
            with db.begin():
                catalog = bootstrap(
                    identities_path=identities,
                    projections_path=projections,
                    ratings_path=ratings,
                    ratings_manifest_path=ratings_manifest,
                    apply=True,
                    db=db,
                    commit=False,
                )
                ratings_result = sync_cfb27_players(db, snapshot=snapshot, season=season, commit=False)
            return {"catalog": catalog, "ratings": ratings_result}
        except Exception:
            db.rollback()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Atomically reconcile the approved preseason player dataset.")
    parser.add_argument("--identities", type=Path, default=DEFAULT_IDENTITIES)
    parser.add_argument("--projections", type=Path, default=DEFAULT_PROJECTIONS)
    parser.add_argument("--ratings", type=Path, default=DEFAULT_RATINGS)
    parser.add_argument("--ratings-manifest", type=Path, default=DEFAULT_RATINGS_MANIFEST)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(
        reconcile(
            identities=args.identities.resolve(),
            projections=args.projections.resolve(),
            ratings=args.ratings.resolve(),
            ratings_manifest=args.ratings_manifest.resolve(),
            season=args.season,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
