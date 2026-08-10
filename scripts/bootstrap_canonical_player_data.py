#!/usr/bin/env python3
"""Bootstrap the reviewed preseason player catalog from checked-in snapshots.

Migrations establish schema only.  The public player universe must come from the
reviewed identity and projection snapshots, never from the retired CFB ratings
seed.  This command is deliberately offline and idempotent so a clean release
database receives the same approved pool as an existing beta database.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.cfb27_player_sync import (
    Cfb27Rating,
    cfb27_identity_key,
    load_reviewed_cfb27_snapshot,
)
from collegefootballfantasy_api.app.services.player_bio import normalize_sheet_player_class
from collegefootballfantasy_api.app.services.power4 import resolve_power4_school
from scripts.audit_annual_projection_scoring import canonical_projection_points
from scripts.audit_preseason_source_contract import require_valid_contract, require_valid_source_directory


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_IDENTITIES = ROOT_DIR / "reports" / "source-imports" / "2026" / "player-identities.csv"
DEFAULT_PROJECTIONS = ROOT_DIR / "reports" / "source-imports" / "2026" / "player-projections.csv"
SOURCE_PREFIX = "canonical-preseason:2026:"
# A player can remain in the database because an older preseason snapshot, a
# past draft, or a roster record references it.  That does not make the player
# part of the reviewed *current* player universe.  Keep the provenance intact
# while moving the source marker out of the canonical eligibility namespace.
LEGACY_SOURCE_PREFIX = "legacy-canonical-preseason:2026:"
ELIGIBLE_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "K"})

PROJECTION_COLUMNS = {
    "COMP.": "pass_completions",
    "ATTEMPTS": "pass_attempts",
    "PASS YDS": "pass_yards",
    "PASS TDS": "pass_tds",
    "INTS": "interceptions",
    "RUSH YDS": "rush_yards",
    "RUSH TDS": "rush_tds",
    "RECEPTIONS": "receptions",
    "REC YDS": "rec_yards",
    "REC TDS": "rec_tds",
    "FG": "fg",
    "XP": "xp",
}


@dataclass(frozen=True)
class CanonicalCatalogSource:
    """Validated source state shared by mutation and zero-write planning."""

    source_contract: dict
    source_batch_id: str
    projections_by_key: dict[tuple[str, str, str], dict[str, str]]
    reviewed_rows: list[dict[str, str]]
    ratings_by_key: dict[str, Cfb27Rating]


def normalize(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", normalized.casefold())


def normalize_position(value: str | None) -> str | None:
    candidate = (value or "").strip().upper()
    for position in ELIGIBLE_POSITIONS:
        if candidate.startswith(position):
            return position
    return None


def canonical_school(value: str | None) -> str:
    school = (value or "").strip()
    return resolve_power4_school(school) or school


def identity_key(name: str | None, school: str | None, position: str | None) -> tuple[str, str, str]:
    return normalize(name), normalize(canonical_school(school)), normalize_position(position) or ""


def as_number(value: str | None) -> float:
    try:
        return float((value or "0").replace(",", ""))
    except ValueError:
        return 0.0


def projection_stats_for_row(projection: dict[str, str]) -> dict[str, float | int | str]:
    """Create a display-ready annual projection from canonical components.

    The source workbook's ``FANTASY PROJ.`` value is retained for auditability,
    but never substituted for the app's standard-scoring total.
    """

    canonical_points = canonical_projection_points(projection)
    if canonical_points is None:
        raise ValueError(
            "Annual projection cannot be scored under component_stats_canonical_scoring_v2_beta_flat_kicker; "
            "the source FANTASY PROJ. value is not a canonical fallback."
        )
    stats: dict[str, float | int | str] = {
        target: as_number(projection.get(source)) for source, target in PROJECTION_COLUMNS.items()
    }
    stats.update(
        {
            "fpts": canonical_points,
            "source_fantasy_proj": as_number(projection.get("FANTASY PROJ.")),
            "scoring_policy_version": "component_stats_canonical_scoring_v2_beta_flat_kicker",
            "projection_season": 2026,
        }
    )
    return stats


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_catalog_source(
    *, identities_path: Path, projections_path: Path, ratings_path: Path | None = None,
    ratings_manifest_path: Path | None = None,
) -> CanonicalCatalogSource:
    """Validate immutable sources without staging ORM mutations."""

    identity_rows = read_rows(identities_path)
    projection_rows = read_rows(projections_path)
    source_contract = require_valid_contract(projection_rows, identity_rows)
    source_directory = require_valid_source_directory(identities_path.parent)
    source_batch_id = source_directory["gate_context"]["source_provenance"]["export_batch_id"]
    if not isinstance(source_batch_id, str) or not source_batch_id.strip():
        raise ValueError("Canonical player bootstrap requires a manifest-backed source batch ID.")
    projections_by_key = {
        identity_key(row.get("PLAYER"), row.get("TEAM"), row.get("POSITION")): row
        for row in projection_rows
        if all(identity_key(row.get("PLAYER"), row.get("TEAM"), row.get("POSITION")))
    }
    unscorable_projection_keys = [
        key for key, row in projections_by_key.items() if canonical_projection_points(row) is None
    ]
    if unscorable_projection_keys:
        raise ValueError(
            "Canonical player bootstrap is blocked because "
            f"{len(unscorable_projection_keys)} annual projections cannot be scored under "
            "component_stats_canonical_scoring_v2_beta_flat_kicker. Supply the required component detail; "
            "the source FANTASY PROJ. value is not a canonical fallback."
        )
    reviewed_rows = [
        row
        for row in identity_rows
        if identity_key(row.get("NAME"), row.get("SCHOOL"), row.get("POSITION")) in projections_by_key
    ]
    ratings_by_key: dict[str, Cfb27Rating] = {}
    if ratings_path is not None:
        if ratings_manifest_path is None:
            raise ValueError("CFB27 ratings import requires an approved snapshot manifest.")
        snapshot = load_reviewed_cfb27_snapshot(
            snapshot_path=ratings_path, manifest_path=ratings_manifest_path,
        )
        ratings_by_key = {
            cfb27_identity_key(name=rating.name, school=rating.school, position=rating.position): rating
            for rating in snapshot.ratings
        }
    return CanonicalCatalogSource(
        source_contract=source_contract,
        source_batch_id=source_batch_id,
        projections_by_key=projections_by_key,
        reviewed_rows=reviewed_rows,
        ratings_by_key=ratings_by_key,
    )


def plan_bootstrap(
    *, identities_path: Path, projections_path: Path, ratings_path: Path | None = None,
    ratings_manifest_path: Path | None = None, db: Session,
) -> dict[str, int | str]:
    """Return the exact bootstrap plan without adding, mutating, or flushing ORM rows."""

    source = load_catalog_source(
        identities_path=identities_path,
        projections_path=projections_path,
        ratings_path=ratings_path,
        ratings_manifest_path=ratings_manifest_path,
    )
    ensure_models_registered()
    existing = {
        identity_key(player.name, player.school, player.position): player
        for player in db.scalars(select(Player)).all()
    }
    reviewed_keys = {
        identity_key(row.get("NAME"), row.get("SCHOOL"), row.get("POSITION"))
        for row in source.reviewed_rows
    }
    created = sum(key not in existing for key in reviewed_keys)
    legacy_snapshot_players = sum(
        1
        for key, player in existing.items()
        if (player.sheet_source_sheet_id or "").strip().startswith(SOURCE_PREFIX)
        and key not in source.projections_by_key
    )
    ratings_matched = sum(
        cfb27_identity_key(
            name=(row.get("NAME") or "").strip(),
            school=canonical_school(row.get("SCHOOL")),
            position=normalize_position(row.get("POSITION")),
        ) in source.ratings_by_key
        for row in source.reviewed_rows
    )
    return {
        "reviewed_rows": len(source.reviewed_rows),
        "eligible_players": len(source.reviewed_rows),
        "source_contract_approved_players": int(source.source_contract["approved_player_count"]),
        "created": created,
        "updated": len(source.reviewed_rows) - created,
        "ratings_matched": ratings_matched,
        "legacy_snapshot_players_excluded_from_current_pool": legacy_snapshot_players,
        "source_batch_id": source.source_batch_id,
    }


def planned_active_cfb27_identities(
    *, identities_path: Path, projections_path: Path
) -> tuple[tuple[str, str, str], ...]:
    """Return the post-bootstrap CFB27 identities without staging ORM rows.

    The catalog bootstrap can replace an old canonical identity with a newly
    approved source identity in the same transaction. A dry run must validate
    ratings against that *planned* pool, rather than the pre-bootstrap rows in
    the database, but may not add or flush the replacement player merely to do
    so.
    """

    source = load_catalog_source(
        identities_path=identities_path,
        projections_path=projections_path,
    )
    identities: list[tuple[str, str, str]] = []
    for row in source.reviewed_rows:
        name = (row.get("NAME") or "").strip()
        school = canonical_school(row.get("SCHOOL"))
        position = normalize_position(row.get("POSITION"))
        if not name or not school or position is None:
            continue
        identities.append((name, school, position))
    return tuple(identities)


def bootstrap(
    *, identities_path: Path, projections_path: Path, ratings_path: Path | None = None,
    ratings_manifest_path: Path | None = None, apply: bool, db: Session | None = None, commit: bool = True,
) -> dict[str, int | str]:
    source = load_catalog_source(
        identities_path=identities_path,
        projections_path=projections_path,
        ratings_path=ratings_path,
        ratings_manifest_path=ratings_manifest_path,
    )

    ensure_models_registered()
    now = datetime.now(timezone.utc)
    created = updated = ratings_matched = 0
    legacy_snapshot_players = 0
    with (SessionLocal() if db is None else nullcontext(db)) as db:
        existing = {
            identity_key(player.name, player.school, player.position): player
            for player in db.scalars(select(Player)).all()
        }
        for identity in source.reviewed_rows:
            key = identity_key(identity.get("NAME"), identity.get("SCHOOL"), identity.get("POSITION"))
            projection = source.projections_by_key[key]
            name = (identity.get("NAME") or "").strip()
            school = canonical_school(identity.get("SCHOOL"))
            position = normalize_position(identity.get("POSITION"))
            if not name or not school or position is None:
                continue

            player = existing.get(key)
            if player is None:
                player = Player(name=name, school=school, position=position)
                db.add(player)
                existing[key] = player
                created += 1
            else:
                updated += 1

            raw_class = (identity.get("CLASS") or "").strip() or None
            source_sheet = (identity.get("source_sheet") or "unknown").strip()
            projection_stats = projection_stats_for_row(projection)
            player.name = name
            player.school = school
            player.position = position
            player.sheet_bio_height = (identity.get("HEIGHT") or "").strip() or None
            player.sheet_bio_weight = (identity.get("WEIGHT") or "").strip() or None
            player.sheet_bio_class = raw_class
            player.sheet_bio_birthplace = (identity.get("BIRTHPLACE") or "").strip() or None
            player.sheet_bio_source_sheet_id = f"{SOURCE_PREFIX}{source_sheet}"
            player.sheet_bio_synced_at = now
            player.player_class = normalize_sheet_player_class(raw_class) or player.player_class
            player.sheet_projected_season_points = projection_stats["fpts"]
            player.sheet_projection_stats = projection_stats
            player.sheet_source_sheet_id = (
                f"canonical-preseason:2026:{source.source_batch_id}:{projection.get('source_sheet') or 'unknown'}"
            )
            player.sheet_synced_at = now

            rating = source.ratings_by_key.get(cfb27_identity_key(name=name, school=school, position=position))
            if rating is not None:
                player.cfb27_rank = rating.rank
                player.cfb27_overall = rating.overall
                player.cfb27_position_rank = rating.position_rank
                player.cfb27_synced_at = now
                ratings_matched += 1

        # The source snapshot is the authoritative public-beta pool.  Preserve
        # legacy records (and their historical foreign-key relationships), but
        # ensure a player omitted from the current approved snapshot cannot
        # remain draftable merely because it was imported by an older snapshot.
        for player in existing.values():
            source_marker = (player.sheet_source_sheet_id or "").strip()
            if not source_marker.startswith(SOURCE_PREFIX):
                continue
            key = identity_key(player.name, player.school, player.position)
            if key in source.projections_by_key:
                continue
            player.sheet_source_sheet_id = (
                f"{LEGACY_SOURCE_PREFIX}{source_marker.removeprefix(SOURCE_PREFIX)}"
            )
            legacy_snapshot_players += 1

        if not apply:
            db.rollback()
        elif commit:
            db.commit()
        else:
            db.flush()

        eligible_count = sum(
            1
            for row in source.reviewed_rows
            if source.projections_by_key.get(identity_key(row.get("NAME"), row.get("SCHOOL"), row.get("POSITION")))
        )

    if eligible_count == 0:
        raise RuntimeError("Canonical player bootstrap found no reviewed players with seasonal projections.")
    return {
        "reviewed_rows": len(source.reviewed_rows),
        "eligible_players": eligible_count,
        "source_contract_approved_players": int(source.source_contract["approved_player_count"]),
        "created": created,
        "updated": updated,
        "ratings_matched": ratings_matched,
        "legacy_snapshot_players_excluded_from_current_pool": legacy_snapshot_players,
        "source_batch_id": source.source_batch_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the offline reviewed 2026 player catalog.")
    parser.add_argument("--identities", type=Path, default=DEFAULT_IDENTITIES)
    parser.add_argument("--projections", type=Path, default=DEFAULT_PROJECTIONS)
    parser.add_argument(
        "--ratings",
        type=Path,
        help="Optional reviewed CFB27 rating snapshot captured from the configured CFB27 Ratings Sheet.",
    )
    parser.add_argument("--ratings-manifest", type=Path, help="Approved immutable manifest for --ratings.")
    parser.add_argument("--apply", action="store_true", help="Persist the idempotent bootstrap instead of validating it.")
    args = parser.parse_args()
    if not args.identities.is_file() or not args.projections.is_file():
        raise SystemExit("Reviewed player identity and projection snapshots must be present in the release artifact.")
    if (
        args.identities.name != "player-identities.csv"
        or args.projections.name != "player-projections.csv"
        or args.identities.parent != args.projections.parent
    ):
        raise SystemExit(
            "Canonical bootstrap requires sibling player-identities.csv and player-projections.csv files from one versioned source directory."
        )
    try:
        require_valid_source_directory(args.identities.parent)
    except ValueError as error:
        raise SystemExit(f"canonical player bootstrap rejected: {error}") from error
    if args.ratings is not None and not args.ratings.is_file():
        raise SystemExit("Reviewed CFB27 rating snapshot does not exist.")
    if args.ratings is not None and args.ratings_manifest is None:
        raise SystemExit("Reviewed CFB27 ratings require --ratings-manifest.")
    print(
        bootstrap(
            identities_path=args.identities,
            projections_path=args.projections,
            ratings_path=args.ratings,
            ratings_manifest_path=args.ratings_manifest,
            apply=args.apply,
        )
    )


if __name__ == "__main__":
    main()
