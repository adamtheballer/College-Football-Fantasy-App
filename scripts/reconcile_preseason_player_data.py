#!/usr/bin/env python3
"""Apply the reviewed preseason player universe in one database transaction.

This is the only release command allowed to mutate identity, projection,
eligibility, CFB27, and preseason-value state. Runtime startup verifies source
artifacts but never invokes this command.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.player import Player
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
    plan_bootstrap,
)


DEFAULT_RATINGS = ROOT_DIR / "api" / "app" / "data" / "cfb27_ratings_2026-08-05.csv"
DEFAULT_RATINGS_MANIFEST = ROOT_DIR / "api" / "app" / "data" / "cfb27_ratings_2026-08-05.manifest.json"
def verify_wayne_knight_postcondition(
    db, *, season: int, source_batch_id: str
) -> dict[str, object]:
    """Fail the shared reconciliation unless the reviewed Wayne row survives intact."""

    if not source_batch_id.strip():
        raise RuntimeError("Wayne Knight reconciliation requires a manifest-backed source batch ID.")

    rows = (
        db.query(Player)
        .filter(Player.name == "Wayne Knight", Player.school == "UCLA", Player.position == "RB")
        .all()
    )
    if len(rows) != 1:
        raise RuntimeError(f"Wayne Knight reconciliation requires exactly one UCLA RB identity; found {len(rows)}.")
    player = rows[0]
    source_marker = player.sheet_source_sheet_id or ""
    expected_marker = f"canonical-preseason:{int(season)}:{source_batch_id}:Big10"
    if source_marker != expected_marker:
        raise RuntimeError(f"Wayne Knight projection source batch mismatch: expected {expected_marker!r}, got {source_marker!r}.")
    if player.sheet_projected_season_points is None or not math.isclose(player.sheet_projected_season_points, 265.0):
        raise RuntimeError(
            f"Wayne Knight season projection postcondition failed: expected 265, got {player.sheet_projected_season_points!r}."
        )
    stats = player.sheet_projection_stats or {}
    expected_stats = {
        "rush_yards": 1300.0,
        "rush_tds": 12.0,
        "receptions": 28.0,
        "rec_yards": 230.0,
        "rec_tds": 2.0,
    }
    for field, expected in expected_stats.items():
        value = stats.get(field)
        if not isinstance(value, (int, float)) or not math.isclose(float(value), expected):
            raise RuntimeError(f"Wayne Knight projection stat {field!r} must equal {expected:g}, got {value!r}.")
    same_name_rows = db.query(Player).filter(Player.name == "Wayne Knight", Player.school == "UCLA").all()
    active_batch_rows = [
        candidate
        for candidate in same_name_rows
        if (candidate.sheet_source_sheet_id or "").startswith(
            f"canonical-preseason:{int(season)}:{source_batch_id}:"
        )
    ]
    if len(active_batch_rows) != 1 or active_batch_rows[0].id != player.id:
        raise RuntimeError("A legacy Wayne Knight identity cannot own the approved current projection batch.")
    return {
        "canonical_player_id": player.id,
        "name": player.name,
        "school": player.school,
        "position": player.position,
        "source_batch_id": source_batch_id,
        "sheet_projected_season_points": player.sheet_projected_season_points,
        "draft_eligible": source_marker.startswith(f"canonical-preseason:{int(season)}:"),
    }


def verify_wayne_knight_dry_run_postcondition(
    db, *, season: int, source_batch_id: str, source_contract: dict, catalog: dict[str, object],
) -> dict[str, object]:
    """Validate the intended Wayne result without adding a Player or flushing the session."""

    source_wayne = source_contract.get("wayne_knight_projection_integrity")
    if not isinstance(source_wayne, dict) or source_wayne.get("status") != "PASS":
        raise RuntimeError("Wayne Knight source contract must pass before a dry-run reconciliation.")
    projection = source_wayne.get("projection")
    if not isinstance(projection, dict):
        raise RuntimeError("Wayne Knight source contract is missing its projection components.")
    expected_stats = {
        "rush_yards": 1300.0,
        "rush_tds": 12.0,
        "receptions": 28.0,
        "rec_yards": 230.0,
        "rec_tds": 2.0,
    }
    if projection.get("name") != "Wayne Knight" or projection.get("team") != "UCLA" or projection.get("position") != "RB":
        raise RuntimeError("Wayne Knight source identity must remain UCLA RB.")
    if not math.isclose(float(projection.get("fantasy_points", -1)), 265.0):
        raise RuntimeError("Wayne Knight source projection must equal 265.")
    for field, expected in expected_stats.items():
        value = projection.get(field)
        if not isinstance(value, (int, float)) or not math.isclose(float(value), expected):
            raise RuntimeError(f"Wayne Knight source stat {field!r} must equal {expected:g}, got {value!r}.")
    if catalog.get("source_batch_id") != source_batch_id:
        raise RuntimeError("Wayne Knight dry-run catalog must use the approved source batch.")
    rows = (
        db.query(Player)
        .filter(Player.name == "Wayne Knight", Player.school == "UCLA", Player.position == "RB")
        .all()
    )
    if len(rows) > 1:
        raise RuntimeError(f"Wayne Knight reconciliation requires at most one existing UCLA RB identity; found {len(rows)}.")
    return {
        "canonical_player_id": rows[0].id if rows else None,
        "name": "Wayne Knight",
        "school": "UCLA",
        "position": "RB",
        "source_batch_id": source_batch_id,
        "sheet_projected_season_points": 265.0,
        "draft_eligible": True,
        "would_create": not rows,
    }


def reconcile(*, identities: Path, projections: Path, ratings: Path, ratings_manifest: Path, season: int, dry_run: bool) -> dict[str, object]:
    """Reconcile every player-data source as one all-or-nothing release unit."""
    source_contract = require_valid_source_directory(identities.parent)
    wayne_source_contract = source_contract["wayne_knight_projection_integrity"]
    source_provenance = source_contract["gate_context"]["source_provenance"]
    source_batch_id = source_provenance.get("export_batch_id")
    if wayne_source_contract.get("status") != "PASS" or not isinstance(source_batch_id, str) or not source_batch_id.strip():
        raise RuntimeError("Wayne Knight source sentinel or immutable source provenance failed validation.")
    snapshot = load_reviewed_cfb27_snapshot(snapshot_path=ratings, manifest_path=ratings_manifest)
    with SessionLocal() as db:
        if dry_run:
            try:
                catalog = plan_bootstrap(
                    identities_path=identities,
                    projections_path=projections,
                    ratings_path=ratings,
                    ratings_manifest_path=ratings_manifest,
                    db=db,
                )
                wayne_integrity = verify_wayne_knight_dry_run_postcondition(
                    db,
                    season=season,
                    source_batch_id=source_batch_id,
                    source_contract=source_contract,
                    catalog=catalog,
                )
                ratings_result = sync_cfb27_players(db, snapshot=snapshot, dry_run=True, season=season, commit=False)
                return {"catalog": catalog, "wayne_knight": wayne_integrity, "ratings": ratings_result}
            finally:
                db.rollback()

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
                wayne_integrity = verify_wayne_knight_postcondition(
                    db, season=season, source_batch_id=source_batch_id
                )
            return {"catalog": catalog, "wayne_knight": wayne_integrity, "ratings": ratings_result}
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
