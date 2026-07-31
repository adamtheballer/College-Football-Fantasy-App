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
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.cfb27_player_sync import (
    cfb27_identity_key,
    load_cfb27_ratings,
)
from collegefootballfantasy_api.app.services.player_bio import normalize_sheet_player_class
from collegefootballfantasy_api.app.services.power4 import resolve_power4_school
from scripts.audit_preseason_source_contract import require_valid_contract, require_valid_source_directory


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_IDENTITIES = ROOT_DIR / "reports" / "source-imports" / "2026" / "player-identities.csv"
DEFAULT_PROJECTIONS = ROOT_DIR / "reports" / "source-imports" / "2026" / "player-projections.csv"
SOURCE_PREFIX = "canonical-preseason:2026:"
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


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bootstrap(*, identities_path: Path, projections_path: Path, apply: bool) -> dict[str, int]:
    identity_rows = read_rows(identities_path)
    projection_rows = read_rows(projections_path)
    source_contract = require_valid_contract(projection_rows, identity_rows)
    projections_by_key = {
        identity_key(row.get("PLAYER"), row.get("TEAM"), row.get("POSITION")): row
        for row in projection_rows
        if all(identity_key(row.get("PLAYER"), row.get("TEAM"), row.get("POSITION")))
    }
    reviewed_rows = [
        row
        for row in identity_rows
        if identity_key(row.get("NAME"), row.get("SCHOOL"), row.get("POSITION")) in projections_by_key
    ]
    ratings_by_key = {
        cfb27_identity_key(name=rating.name, school=rating.school, position=rating.position): rating
        for rating in load_cfb27_ratings()
    }

    ensure_models_registered()
    now = datetime.now(timezone.utc)
    created = updated = ratings_matched = 0
    with SessionLocal() as db:
        existing = {
            identity_key(player.name, player.school, player.position): player
            for player in db.scalars(select(Player)).all()
        }
        for identity in reviewed_rows:
            key = identity_key(identity.get("NAME"), identity.get("SCHOOL"), identity.get("POSITION"))
            projection = projections_by_key[key]
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
            projection_stats = {
                target: as_number(projection.get(source)) for source, target in PROJECTION_COLUMNS.items()
            }
            projection_stats.update(
                {
                    "fpts": as_number(projection.get("FANTASY PROJ.")),
                    "projection_season": 2026,
                }
            )
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
            player.sheet_source_sheet_id = f"canonical-preseason:2026:{projection.get('source_sheet') or 'unknown'}"
            player.sheet_synced_at = now

            rating = ratings_by_key.get(cfb27_identity_key(name=name, school=school, position=position))
            if rating is not None:
                player.cfb27_rank = rating.rank
                player.cfb27_overall = rating.overall
                player.cfb27_position_rank = rating.position_rank
                player.cfb27_synced_at = now
                ratings_matched += 1

        if not apply:
            db.rollback()
        else:
            db.commit()

        eligible_count = sum(
            1
            for row in reviewed_rows
            if projections_by_key.get(identity_key(row.get("NAME"), row.get("SCHOOL"), row.get("POSITION")))
        )

    if eligible_count == 0:
        raise RuntimeError("Canonical player bootstrap found no reviewed players with seasonal projections.")
    return {
        "reviewed_rows": len(reviewed_rows),
        "eligible_players": eligible_count,
        "source_contract_approved_players": int(source_contract["approved_player_count"]),
        "created": created,
        "updated": updated,
        "ratings_matched": ratings_matched,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the offline reviewed 2026 player catalog.")
    parser.add_argument("--identities", type=Path, default=DEFAULT_IDENTITIES)
    parser.add_argument("--projections", type=Path, default=DEFAULT_PROJECTIONS)
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
    print(bootstrap(identities_path=args.identities, projections_path=args.projections, apply=args.apply))


if __name__ == "__main__":
    main()



