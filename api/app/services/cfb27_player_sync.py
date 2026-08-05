from __future__ import annotations

import json
import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.player_pool_filters import (
    active_canonical_preseason_player_filter,
    generated_test_player_filter,
    is_approved_fantasy_school,
)

_MODEL_REGISTRY = (League, Player, RosterEntry, Team, User)


# Read-only callers use the same frozen release artifact as the importer.  The
# older JSON seed remains only for historical migrations.
CFB27_SOURCE_PATH = Path(__file__).resolve().parents[1] / "data" / "cfb27_ratings_2026-08-05.csv"
CFB27_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
CFB27_SCHOOL_ALIASES = {"california": "cal"}
# The imported CFB27 source only contains real game overalls.  A board rank
# (for example, 33) is never a player overall and must not be allowed through
# this import path as an OVR value.
# The approved workbook includes eligible depth players below 70. Its verified
# floor is 62; values below that are board ranks or malformed source data, not
# an approved CFB27 player overall.
CFB27_MIN_OVERALL = 62
CFB27_MAX_OVERALL = 99


@dataclass(frozen=True)
class Cfb27Rating:
    rank: int
    position_rank: int
    name: str
    school: str
    position: str
    overall: int


@dataclass(frozen=True)
class ReviewedCfb27Snapshot:
    """An immutable, approved CFB27 export validated before any database write."""

    snapshot_path: Path
    manifest_path: Path
    spreadsheet_id: str
    retrieved_at: str
    sha256: str
    row_count: int
    approval_status: str
    dataset_version: str
    export_batch_id: str
    tabs: tuple[tuple[str, int], ...]
    ratings: tuple[Cfb27Rating, ...]


def normalize_cfb27_identity_text(value: str | None) -> str:
    normalized = (value or "").lower().replace("&", "and")
    # Suffixes are part of the approved identity.  Stripping them conflates
    # distinct players such as "Harry Dalton" and "Harry Dalton III" and can
    # cause a ratings import to update the wrong canonical record.
    return re.sub(r"[^a-z0-9]+", "", normalized).strip()


def normalize_cfb27_school(value: str | None) -> str:
    normalized = normalize_cfb27_identity_text(value)
    return CFB27_SCHOOL_ALIASES.get(normalized, normalized)


def cfb27_identity_key(*, name: str | None, school: str | None, position: str | None) -> str:
    return "|".join(
        [
            normalize_cfb27_identity_text(name),
            normalize_cfb27_school(school),
            (position or "").strip().upper(),
        ]
    )


def _parse_cfb27_rating_rows(source: object, *, source_label: str) -> tuple[Cfb27Rating, ...]:
    if not isinstance(source, list):
        raise ValueError(f"CFB27 source {source_label} must contain a JSON list of reviewed rating rows.")
    normalized_rows = []
    for index, row in enumerate(source, start=1):
        overall = int(row["overall"])
        if not CFB27_MIN_OVERALL <= overall <= CFB27_MAX_OVERALL:
            raise ValueError(
                f"CFB27 row {index} has invalid overall {overall}; "
                f"expected {CFB27_MIN_OVERALL}-{CFB27_MAX_OVERALL}"
            )
        position = str(row["position"]).upper()
        if position not in CFB27_POSITIONS:
            raise ValueError(f"CFB27 row {index} has unsupported fantasy position {position!r}.")
        normalized_rows.append(
            {
                "source_order": index - 1,
                "position_rank": int(row.get("rank") or 0),
                "name": str(row["name"]),
                "school": str(row["school"]),
                "position": position,
                "overall": overall,
            }
        )
    # The reviewed Sheets export can omit an EA-specific position rank.  An
    # app rank is then derived deterministically from the immutable export's
    # OVR/order, without inventing or changing any rating value.
    position_order: dict[str, int] = {}
    for row in sorted(normalized_rows, key=lambda item: (str(item["position"]), -int(item["overall"]), int(item["source_order"]))):
        position = str(row["position"])
        position_order[position] = position_order.get(position, 0) + 1
        if int(row["position_rank"]) <= 0:
            row["position_rank"] = position_order[position]
    global_rank_by_key = {
        cfb27_identity_key(name=row["name"], school=row["school"], position=row["position"]): index + 1
        for index, row in enumerate(
            sorted(normalized_rows, key=lambda row: (-int(row["overall"]), int(row["source_order"])))
        )
    }
    return tuple(
        Cfb27Rating(
            rank=global_rank_by_key[
                cfb27_identity_key(name=str(row["name"]), school=str(row["school"]), position=str(row["position"]))
            ],
            position_rank=int(row["position_rank"]),
            name=str(row["name"]),
            school=str(row["school"]),
            position=str(row["position"]),
            overall=int(row["overall"]),
        )
        for row in normalized_rows
    )


@lru_cache(maxsize=4)
def _load_cfb27_ratings_for_source(source_path: str) -> tuple[Cfb27Rating, ...]:
    return load_cfb27_ratings_from_snapshot(Path(source_path))


def load_cfb27_ratings() -> tuple[Cfb27Rating, ...]:
    """Compatibility loader for the legacy packaged snapshot only.

    New player bootstrap and release imports must call
    :func:`load_cfb27_ratings_from_snapshot` with the approved Sheets export.
    Keeping this loader avoids an API break for existing read-only consumers
    while the import path is migrated away from this historical seed file.
    """

    # Cache by the resolved source, rather than by an empty argument list.
    # This prevents a temporary importer/test snapshot from contaminating
    # later reads after CFB27_SOURCE_PATH is restored.
    return _load_cfb27_ratings_for_source(str(CFB27_SOURCE_PATH.resolve()))


load_cfb27_ratings.cache_clear = _load_cfb27_ratings_for_source.cache_clear  # type: ignore[attr-defined]


def _column(row: dict[str, str], *candidates: str) -> str:
    normalized = {re.sub(r"[^a-z0-9]+", "", key.casefold()): value for key, value in row.items()}
    for candidate in candidates:
        value = normalized.get(re.sub(r"[^a-z0-9]+", "", candidate.casefold()))
        if value is not None:
            return value.strip()
    return ""


def _parse_cfb27_csv_snapshot(path: Path) -> tuple[Cfb27Rating, ...]:
    """Read a flattened, captured export of the approved ratings workbook.

    The workbook's conference tabs are visually grouped by team.  The capture
    step must flatten those groups into explicit TEAM/PLAYER/EA POSITION/OVR
    columns before this importer runs; guessing a team from an adjacent header
    would make a release import non-reproducible.
    """

    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    normalized_rows: list[dict[str, object]] = []
    for row_number, row in enumerate(rows, start=2):
        name = _column(row, "PLAYER", "NAME")
        school = _column(row, "TEAM", "SCHOOL")
        position = _column(row, "EA POSITION", "POSITION")
        overall = _column(row, "OVR", "OVERALL")
        if not all((name, school, position, overall)):
            raise ValueError(
                f"CFB27 ratings snapshot row {row_number} must include TEAM, PLAYER, EA POSITION, and OVR."
            )
        normalized_rows.append(
            {
                "name": name,
                "school": school,
                "position": position,
                "overall": overall,
                "rank": _column(row, "POSITION RANK", "RANK"),
            }
        )
    return _parse_cfb27_rating_rows(normalized_rows, source_label=str(path))


def load_cfb27_ratings_from_snapshot(path: Path) -> tuple[Cfb27Rating, ...]:
    """Load a reviewed immutable ratings export; never scrape a provider."""

    if path.suffix.casefold() == ".csv":
        return _parse_cfb27_csv_snapshot(path)
    return _parse_cfb27_rating_rows(
        json.loads(path.read_text(encoding="utf-8")), source_label=str(path)
    )


def load_reviewed_cfb27_snapshot(*, snapshot_path: Path, manifest_path: Path) -> ReviewedCfb27Snapshot:
    """Validate a captured ratings export against immutable approval metadata."""

    if not snapshot_path.is_file():
        raise ValueError("CFB27 reviewed snapshot does not exist.")
    if not manifest_path.is_file():
        raise ValueError("CFB27 reviewed snapshot manifest does not exist.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("CFB27 reviewed snapshot manifest is invalid JSON.") from error

    metadata = manifest.get("cfb27_ratings", manifest.get("sources", {}).get("cfb27_ratings"))
    if not isinstance(metadata, dict):
        raise ValueError("CFB27 reviewed snapshot manifest lacks cfb27_ratings metadata.")
    spreadsheet_id = metadata.get("spreadsheet_id")
    retrieved_at = metadata.get("retrieved_at", metadata.get("exported_at_utc"))
    expected_hash = metadata.get("sha256")
    row_count = metadata.get("row_count", metadata.get("record_count"))
    approval_status = metadata.get("approval_status")
    dataset_version = metadata.get("dataset_version")
    export_batch_id = metadata.get("export_batch_id")
    tabs = metadata.get("tabs")
    if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
        raise ValueError("CFB27 reviewed snapshot manifest is missing spreadsheet_id.")
    if not isinstance(retrieved_at, str) or not retrieved_at.strip():
        raise ValueError("CFB27 reviewed snapshot manifest is missing retrieved_at.")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ValueError("CFB27 reviewed snapshot manifest is missing a SHA-256 hash.")
    if not isinstance(row_count, int) or row_count < 1:
        raise ValueError("CFB27 reviewed snapshot manifest is missing a valid row_count.")
    if approval_status != "approved":
        raise ValueError("CFB27 reviewed snapshot is not approved.")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise ValueError("CFB27 reviewed snapshot manifest is missing dataset_version.")
    if not isinstance(export_batch_id, str) or not export_batch_id.strip():
        raise ValueError("CFB27 reviewed snapshot manifest is missing export_batch_id.")
    if not isinstance(tabs, list) or not tabs:
        raise ValueError("CFB27 reviewed snapshot manifest is missing source tabs.")
    normalized_tabs: list[tuple[str, int]] = []
    for tab in tabs:
        if not isinstance(tab, dict) or not isinstance(tab.get("title"), str) or not tab["title"].strip() or not isinstance(tab.get("gid"), int):
            raise ValueError("CFB27 reviewed snapshot manifest has an invalid source tab.")
        normalized_tabs.append((tab["title"].strip(), tab["gid"]))

    actual_hash = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError("CFB27 reviewed snapshot SHA-256 does not match its manifest.")
    ratings = load_cfb27_ratings_from_snapshot(snapshot_path)
    if len(ratings) != row_count:
        raise ValueError("CFB27 reviewed snapshot row_count does not match its manifest.")
    return ReviewedCfb27Snapshot(
        snapshot_path=snapshot_path,
        manifest_path=manifest_path,
        spreadsheet_id=spreadsheet_id,
        retrieved_at=retrieved_at,
        sha256=actual_hash,
        row_count=row_count,
        approval_status=approval_status,
        dataset_version=dataset_version,
        export_batch_id=export_batch_id,
        tabs=tuple(normalized_tabs),
        ratings=ratings,
    )


def _has_rank(player: Player) -> bool:
    return player.sheet_adp is not None and player.sheet_adp > 0


def _canonical_player(candidates: list[Player]) -> Player:
    return sorted(candidates, key=lambda player: (0 if _has_rank(player) else 1, player.id or 0))[0]


def _update_canonical_player(player: Player, rating: Cfb27Rating, *, source_batch_id: str) -> bool:
    changed = False
    cfb27_changed = False
    # Names, schools, positions, and bios belong to the approved identity
    # workbook.  Ratings are an enrichment input only and may never change
    # canonical identity fields after a match has been established.
    # A rating row is not an identity-provider record.  In particular, do not
    # fabricate an external ID from it: the reviewed player-identity Sheet is
    # the only upstream authority for player identity and bios.
    if player.cfb27_rank != rating.rank:
        player.cfb27_rank = rating.rank
        changed = True
        cfb27_changed = True
    if player.cfb27_overall != rating.overall:
        player.cfb27_overall = rating.overall
        changed = True
        cfb27_changed = True
    if player.raw_cfb27_rating != rating.overall:
        player.raw_cfb27_rating = rating.overall
        changed = True
        cfb27_changed = True
    # This importer is only used for the approved preseason reconciliation.
    # The explicit release command checks finalized-week state before calling
    # it, so never allow a historical weekly value to leak into this baseline.
    if player.current_value_rating != float(rating.overall):
        player.current_value_rating = float(rating.overall)
        changed = True
    if player.value_policy_version != "cfb27_exact_preseason_v1":
        player.value_policy_version = "cfb27_exact_preseason_v1"
        changed = True
    if player.value_calculation_week != 0:
        player.value_calculation_week = 0
        changed = True
    if player.value_source_batch_id != source_batch_id:
        player.value_source_batch_id = source_batch_id
        changed = True
    player.value_calculated_at = datetime.now(timezone.utc)
    player.value_input_json = {"raw_cfb27_rating": rating.overall, "source_batch_id": source_batch_id}
    if player.cfb27_position_rank != rating.position_rank:
        player.cfb27_position_rank = rating.position_rank
        changed = True
        cfb27_changed = True
    if cfb27_changed:
        player.cfb27_synced_at = datetime.now(timezone.utc)
    return changed


def _clear_current_batch_rating_from_legacy_player(player: Player) -> bool:
    """Remove only an erroneous preseason CFB27 assignment from a legacy row.

    Legacy player rows are preserved for historical foreign keys.  The value
    source batch is the explicit provenance signal that this immutable CFB27
    batch was incorrectly applied to a legacy row, so no older historical
    value is touched.
    """

    if (
        player.value_policy_version != "cfb27_exact_preseason_v1"
        or player.value_calculation_week != 0
        or not player.value_source_batch_id
    ):
        return False
    player.cfb27_rank = None
    player.cfb27_overall = None
    player.cfb27_position_rank = None
    player.cfb27_synced_at = None
    player.raw_cfb27_rating = None
    player.current_value_rating = None
    player.value_policy_version = None
    player.value_calculation_week = None
    player.value_calculated_at = None
    player.value_source_batch_id = None
    player.value_input_json = None
    return True


def sync_cfb27_players(
    db: Session, *, snapshot: ReviewedCfb27Snapshot | None = None, dry_run: bool = False, season: int = 2026
) -> dict[str, int]:
    """Sync only a reviewed ratings snapshot onto an already-approved pool.

    The ratings sheet has no authority to create or rename player records.  A
    caller must provide a snapshot explicitly so this command cannot silently
    fall back to the retired packaged rating seed.
    """

    if snapshot is None:
        raise RuntimeError(
            "CFB27 sync requires an explicit reviewed ratings snapshot; the legacy packaged JSON is not an import source."
        )
    # A source import may refresh raw ratings, but it must never reset an
    # in-season value.  The lifecycle check is authoritative and fail-closed.
    from collegefootballfantasy_api.app.services.player_trade_value import week_one_is_authoritatively_finalized
    if week_one_is_authoritatively_finalized(db, season=season):
        raise RuntimeError("CFB27 preseason reconciliation is blocked after authoritative Week 1 finalization.")
    # Ratings are valid only for the active, reviewed current snapshot.  Do
    # not let retained legacy rows consume a source rating that belongs to a
    # current draft/waiver identity.
    existing_players = db.query(Player).filter(active_canonical_preseason_player_filter(season)).all()
    players_by_key: dict[str, list[Player]] = {}
    for player in existing_players:
        key = cfb27_identity_key(name=player.name, school=player.school, position=player.position)
        players_by_key.setdefault(key, []).append(player)

    duplicate_keys = sorted(key for key, candidates in players_by_key.items() if len(candidates) > 1)
    # Fail before touching a single row.  Choosing an arbitrary duplicate is
    # not a reconciliation; it is a data-corruption risk.
    ratings_by_key: dict[str, list[Cfb27Rating]] = {}
    for rating in snapshot.ratings:
        if not is_approved_fantasy_school(rating.school):
            continue
        key = cfb27_identity_key(name=rating.name, school=rating.school, position=rating.position)
        ratings_by_key.setdefault(key, []).append(rating)
    snapshot_keys = set(ratings_by_key)
    duplicate_source_keys = sorted(key for key, rows in ratings_by_key.items() if len(rows) > 1)
    if duplicate_source_keys:
        raise ValueError(f"CFB27 sync blocked by duplicate approved source identities: {', '.join(duplicate_source_keys)}")
    conflicting_keys = sorted(set(duplicate_keys).intersection(snapshot_keys))
    if conflicting_keys:
        raise ValueError(f"CFB27 sync blocked by duplicate canonical identities: {', '.join(conflicting_keys)}")

    active_keys = set(players_by_key)
    matched_keys = sorted(active_keys.intersection(snapshot_keys))
    missing_current_keys = sorted(active_keys.difference(snapshot_keys))
    unused_source_keys = sorted(snapshot_keys.difference(active_keys))
    legacy_assignments = (
        db.query(Player)
        .filter(generated_test_player_filter())
        .filter(Player.sheet_source_sheet_id.like(f"legacy-canonical-preseason:{int(season)}:%"))
        # A corrected immutable export receives a new batch ID.  Clear only
        # old preseason CFB27 values that were attached to retained legacy
        # identities; never touch an in-season or differently governed value.
        .filter(Player.value_policy_version == "cfb27_exact_preseason_v1")
        .filter(Player.value_calculation_week == 0)
        .filter(Player.value_source_batch_id.isnot(None))
        .all()
    )
    result = {
        "created": 0,
        "updated": 0,
        "already_present": len(matched_keys),
        "matched": len(matched_keys),
        "current_eligible_players": len(active_keys),
        "missing": len(missing_current_keys),
        "missing_current_players": len(missing_current_keys),
        "unmatched_approved": len(unused_source_keys),
        "unused_source_rows": len(unused_source_keys),
        "skipped_non_power4": len(snapshot.ratings) - len(snapshot_keys),
        "duplicate_matches": 0,
        "duplicate_current_identities": len(duplicate_keys),
        "duplicate_source_rows": len(duplicate_source_keys),
        "legacy_assignments_to_clear": len(legacy_assignments),
        "manual_review_rows": len(missing_current_keys),
        "total": snapshot.row_count,
    }

    # A partial result is audit evidence, never permission to mutate a player
    # pool.  Exact composite identity is intentionally required; no aliases or
    # fuzzy name matching may paper over a source discrepancy.
    if missing_current_keys or unused_source_keys:
        if dry_run:
            db.rollback()
            return result
        raise ValueError(
            "CFB27 sync blocked by current/source identity mismatch: "
            f"{len(missing_current_keys)} current player(s) missing approved ratings; "
            f"{len(unused_source_keys)} approved rating row(s) unused."
        )

    try:
        if not dry_run:
            for player in legacy_assignments:
                _clear_current_batch_rating_from_legacy_player(player)
            for key in matched_keys:
                player = _canonical_player(players_by_key[key])
                rating = ratings_by_key[key][0]
                if _update_canonical_player(player, rating, source_batch_id=snapshot.export_batch_id):
                    result["updated"] += 1
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    return result
