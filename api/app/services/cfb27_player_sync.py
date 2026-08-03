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
    approved_school_player_filter,
    generated_test_player_filter,
    is_approved_fantasy_school,
)

_MODEL_REGISTRY = (League, Player, RosterEntry, Team, User)


CFB27_SOURCE_PATH = Path(__file__).resolve().parents[1] / "data" / "cfb27_ratings.json"
CFB27_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
CFB27_SCHOOL_ALIASES = {"california": "cal"}
# The imported CFB27 source only contains real game overalls.  A board rank
# (for example, 33) is never a player overall and must not be allowed through
# this import path as an OVR value.
CFB27_MIN_OVERALL = 70
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


@lru_cache(maxsize=1)
def load_cfb27_ratings() -> tuple[Cfb27Rating, ...]:
    """Compatibility loader for the legacy packaged snapshot only.

    New player bootstrap and release imports must call
    :func:`load_cfb27_ratings_from_snapshot` with the approved Sheets export.
    Keeping this loader avoids an API break for existing read-only consumers
    while the import path is migrated away from this historical seed file.
    """

    return _parse_cfb27_rating_rows(
        json.loads(CFB27_SOURCE_PATH.read_text(encoding="utf-8")), source_label=str(CFB27_SOURCE_PATH)
    )


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
        ratings=ratings,
    )


def _has_rank(player: Player) -> bool:
    return player.sheet_adp is not None and player.sheet_adp > 0


def _canonical_player(candidates: list[Player]) -> Player:
    return sorted(candidates, key=lambda player: (0 if _has_rank(player) else 1, player.id or 0))[0]


def _update_canonical_player(player: Player, rating: Cfb27Rating) -> bool:
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
    if player.cfb27_position_rank != rating.position_rank:
        player.cfb27_position_rank = rating.position_rank
        changed = True
        cfb27_changed = True
    if cfb27_changed:
        player.cfb27_synced_at = datetime.now(timezone.utc)
    return changed


def sync_cfb27_players(
    db: Session, *, snapshot: ReviewedCfb27Snapshot | None = None, dry_run: bool = False
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
    existing_players = (
        db.query(Player)
        .filter(generated_test_player_filter(), approved_school_player_filter())
        .filter(Player.position.in_(CFB27_POSITIONS))
        .all()
    )
    players_by_key: dict[str, list[Player]] = {}
    for player in existing_players:
        key = cfb27_identity_key(name=player.name, school=player.school, position=player.position)
        players_by_key.setdefault(key, []).append(player)

    updated = 0
    matched = 0
    duplicate_matches = 0
    unmatched_approved = 0
    skipped_non_power4 = 0
    for rating in snapshot.ratings:
        if not is_approved_fantasy_school(rating.school):
            skipped_non_power4 += 1
            continue
        key = cfb27_identity_key(name=rating.name, school=rating.school, position=rating.position)
        candidates = players_by_key.get(key)
        if candidates:
            matched += 1
            if len(candidates) > 1:
                duplicate_matches += 1
            canonical = _canonical_player(candidates)
            if not dry_run and _update_canonical_player(canonical, rating):
                updated += 1
            continue

        unmatched_approved += 1

    if dry_run:
        db.rollback()
    elif updated:
        db.commit()
    return {
        "created": 0,
        "updated": updated,
        "already_present": matched,
        "matched": matched,
        "missing": unmatched_approved,
        "unmatched_approved": unmatched_approved,
        "skipped_non_power4": skipped_non_power4,
        "duplicate_matches": duplicate_matches,
        "total": snapshot.row_count,
    }
