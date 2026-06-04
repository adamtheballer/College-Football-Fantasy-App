from __future__ import annotations

import csv
import io
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.app.models.player import Player
from api.app.services.player_identity import canonical_player_key, normalize_player_position

GOOGLE_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1NMP3EJSMbdRd7HDA0t7TwxzJ9DM_bUynLoRCgE6Ml74/export?format=csv&gid=0"
SUPPORTED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}

COLUMN_ALIASES: dict[str, set[str]] = {
    "name": {"name", "player", "player_name", "full_name"},
    "position": {"position", "pos"},
    "school": {"school", "team", "college", "college_team", "university"},
    "external_id": {"external_id", "sportsdata_id", "player_id_external", "id"},
    "image_url": {"image_url", "headshot", "photo", "player_image"},
    "rank": {"rank", "overall_rank", "draft_rank", "big_board_rank"},
    "adp": {"adp", "avg_draft_position", "average_draft_position"},
    "projected_fantasy_points": {"projected_fantasy_points", "fantasy_points", "fpts", "proj_points", "projection"},
    "player_class": {"class", "year", "player_class"},
}

PROJECTION_STAT_ALIASES: dict[str, set[str]] = {
    "pass_yards": {"pass_yards", "passing_yards", "pass_yds"},
    "pass_tds": {"pass_tds", "passing_tds", "passing_touchdowns"},
    "interceptions": {"interceptions", "ints", "int"},
    "rush_yards": {"rush_yards", "rushing_yards", "rush_yds"},
    "rush_tds": {"rush_tds", "rushing_tds", "rushing_touchdowns"},
    "receptions": {"receptions", "rec"},
    "rec_yards": {"rec_yards", "receiving_yards", "receiving_yds"},
    "rec_tds": {"rec_tds", "receiving_tds", "receiving_touchdowns"},
    "floor": {"floor"},
    "ceiling": {"ceiling"},
    "boom_prob": {"boom_prob", "boom"},
    "bust_prob": {"bust_prob", "bust"},
}


@dataclass
class ImportIssue:
    row_number: int
    reason: str


@dataclass
class PlayerImportResult:
    received: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    issues: list[ImportIssue] = field(default_factory=list)


def normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def normalize_position(value: str) -> str:
    return normalize_player_position(value)


def stable_player_key(name: str, position: str, school: str) -> tuple[str, str, str]:
    return canonical_player_key(name, position, school)


def resolve_column_mapping(headers: list[str]) -> dict[str, str]:
    normalized_to_original = {normalized_header(header): header for header in headers}
    mapping: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            original = normalized_to_original.get(normalized_header(alias))
            if original:
                mapping[canonical] = original
                break
    return mapping


def resolve_projection_mapping(headers: list[str]) -> dict[str, str]:
    normalized_to_original = {normalized_header(header): header for header in headers}
    mapping: dict[str, str] = {}
    for canonical, aliases in PROJECTION_STAT_ALIASES.items():
        for alias in aliases:
            original = normalized_to_original.get(normalized_header(alias))
            if original:
                mapping[canonical] = original
                break
    return mapping


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def read_csv_rows_from_text(text: str) -> tuple[list[dict[str, str]], list[str]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    return [dict(row or {}) for row in reader], list(reader.fieldnames)


def read_csv_rows_from_path(path: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    return read_csv_rows_from_text(Path(path).read_text(encoding="utf-8-sig"))


def read_csv_rows_from_url(url: str) -> tuple[list[dict[str, str]], list[str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8-sig", errors="replace")
    return read_csv_rows_from_text(body)


def _extract_projection_stats(raw: dict[str, str], mapping: dict[str, str], rank: float | None) -> dict[str, float]:
    stats: dict[str, float] = {}
    if rank is not None:
        stats["rank"] = float(rank)
    for key, header in mapping.items():
        parsed = parse_float(raw.get(header))
        if parsed is not None:
            stats[key] = parsed
    return stats


def _find_existing_player(
    db: Session,
    *,
    external_id: str | None,
    name: str,
    position: str,
    school: str,
) -> Player | None:
    if external_id:
        existing = db.query(Player).filter(Player.external_id == external_id).first()
        if existing:
            return existing
    target_key = canonical_player_key(name, position, school)
    candidates = (
        db.query(Player)
        .filter(
            func.lower(Player.name) == target_key[0],
            func.upper(Player.position) == target_key[1],
        )
        .all()
    )
    return next((player for player in candidates if canonical_player_key(player.name, player.position, player.school) == target_key), None)


def import_players_from_csv_rows(
    db: Session,
    rows: list[dict[str, str]],
    headers: list[str],
    *,
    source: str = "google_sheet",
    dry_run: bool = False,
    limit: int | None = None,
) -> PlayerImportResult:
    mapping = resolve_column_mapping(headers)
    required_missing = [column for column in ("name", "position", "school") if column not in mapping]
    if required_missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(required_missing)}")
    projection_mapping = resolve_projection_mapping(headers)
    result = PlayerImportResult(received=min(len(rows), limit) if limit else len(rows))
    seen_keys: set[tuple[str, str, str] | tuple[str, str]] = set()
    now = datetime.now(timezone.utc)

    for row_number, raw in enumerate(rows[:limit] if limit else rows, start=2):
        name = (raw.get(mapping["name"]) or "").strip()
        position = normalize_position(raw.get(mapping["position"]) or "")
        school = (raw.get(mapping["school"]) or "").strip()
        if not name or not position or not school:
            result.skipped += 1
            result.issues.append(ImportIssue(row_number=row_number, reason="missing required name/position/school"))
            continue
        if position not in SUPPORTED_POSITIONS:
            result.skipped += 1
            result.issues.append(ImportIssue(row_number=row_number, reason=f"unsupported position '{position}'"))
            continue

        external_id = (raw.get(mapping.get("external_id", "")) or "").strip() or None
        dedupe_key: tuple[str, str] | tuple[str, str, str] = (
            ("external_id", external_id) if external_id else stable_player_key(name, position, school)
        )
        if dedupe_key in seen_keys:
            result.skipped += 1
            result.issues.append(ImportIssue(row_number=row_number, reason="duplicate row in import file"))
            continue
        seen_keys.add(dedupe_key)

        rank = parse_float(raw.get(mapping.get("rank", "")))
        adp = parse_float(raw.get(mapping.get("adp", "")))
        projected = parse_float(raw.get(mapping.get("projected_fantasy_points", "")))
        image_url = (raw.get(mapping.get("image_url", "")) or "").strip() or None
        player_class = (raw.get(mapping.get("player_class", "")) or "").strip() or None
        projection_stats = _extract_projection_stats(raw, projection_mapping, rank)
        draft_order_value = adp if adp is not None else rank

        existing = _find_existing_player(
            db,
            external_id=external_id,
            name=name,
            position=position,
            school=school,
        )
        if existing:
            existing.name = name
            existing.position = position
            existing.school = school
            existing.image_url = image_url
            existing.player_class = player_class
            if external_id:
                existing.external_id = external_id
            existing.sheet_adp = draft_order_value
            existing.sheet_projected_season_points = projected
            existing.sheet_projection_stats = projection_stats or None
            existing.sheet_source_sheet_id = source
            existing.sheet_synced_at = now
            db.add(existing)
            result.updated += 1
        else:
            db.add(
                Player(
                    external_id=external_id,
                    name=name,
                    position=position,
                    school=school,
                    image_url=image_url,
                    player_class=player_class,
                    sheet_adp=draft_order_value,
                    sheet_projected_season_points=projected,
                    sheet_projection_stats=projection_stats or None,
                    sheet_source_sheet_id=source,
                    sheet_synced_at=now,
                )
            )
            result.created += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return result
