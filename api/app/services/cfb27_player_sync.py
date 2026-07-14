from __future__ import annotations

import re
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.player_pool_filters import generated_test_player_filter


CFB27_SOURCE_PATH = Path(__file__).resolve().parents[1] / "data" / "cfb27_ratings.json"
CFB27_EXTERNAL_PREFIX = "cfb27:"
CFB27_SOURCE_ID = "cfb27"
CFB27_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


@dataclass(frozen=True)
class Cfb27Rating:
    rank: int
    name: str
    school: str
    position: str
    overall: int


def normalize_cfb27_identity_text(value: str | None) -> str:
    normalized = (value or "").lower().replace("&", "and")
    normalized = re.sub(r"\b(jr|jr\.|iii|ii|iv)\b", "", normalized)
    return re.sub(r"[^a-z0-9]+", "", normalized).strip()


def cfb27_identity_key(*, name: str | None, school: str | None, position: str | None) -> str:
    return "|".join(
        [
            normalize_cfb27_identity_text(name),
            normalize_cfb27_identity_text(school),
            (position or "").strip().upper(),
        ]
    )


@lru_cache(maxsize=1)
def load_cfb27_ratings() -> tuple[Cfb27Rating, ...]:
    source = json.loads(CFB27_SOURCE_PATH.read_text(encoding="utf-8"))
    return tuple(
        Cfb27Rating(
            rank=int(row["rank"]),
            name=str(row["name"]),
            school=str(row["school"]),
            position=str(row["position"]).upper(),
            overall=int(row["overall"]),
        )
        for row in source
    )


def _has_rank(player: Player) -> bool:
    return player.sheet_adp is not None and player.sheet_adp > 0


def _canonical_player(candidates: list[Player]) -> Player:
    return sorted(candidates, key=lambda player: (0 if _has_rank(player) else 1, player.id or 0))[0]


def _update_canonical_player(player: Player, rating: Cfb27Rating) -> bool:
    changed = False
    if player.name != rating.name:
        player.name = rating.name
        changed = True
    if player.school != rating.school:
        player.school = rating.school
        changed = True
    if player.position != rating.position:
        player.position = rating.position
        changed = True
    if not _has_rank(player):
        player.sheet_adp = float(rating.rank)
        changed = True
    if not player.external_id:
        player.external_id = (
            f"{CFB27_EXTERNAL_PREFIX}"
            f"{cfb27_identity_key(name=rating.name, school=rating.school, position=rating.position)}"
        )
        changed = True
    if not player.sheet_source_sheet_id:
        player.sheet_source_sheet_id = CFB27_SOURCE_ID
        changed = True
    return changed


def sync_cfb27_players(db: Session, *, dry_run: bool = False) -> dict[str, int]:
    ratings = load_cfb27_ratings()
    existing_players = (
        db.query(Player)
        .filter(generated_test_player_filter())
        .filter(Player.position.in_(CFB27_POSITIONS))
        .all()
    )
    players_by_key: dict[str, list[Player]] = {}
    for player in existing_players:
        key = cfb27_identity_key(name=player.name, school=player.school, position=player.position)
        players_by_key.setdefault(key, []).append(player)

    created = 0
    updated = 0
    matched = 0
    duplicate_matches = 0
    missing = 0
    for rating in ratings:
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

        missing += 1
        if not dry_run:
            player = Player(
                external_id=f"{CFB27_EXTERNAL_PREFIX}{key}",
                name=rating.name,
                school=rating.school,
                position=rating.position,
                sheet_adp=float(rating.rank),
                sheet_source_sheet_id=CFB27_SOURCE_ID,
            )
            db.add(player)
            players_by_key[key] = [player]
        created += 1

    if dry_run:
        db.rollback()
    elif created or updated:
        db.commit()
    return {
        "created": created,
        "updated": updated,
        "already_present": matched,
        "matched": matched,
        "missing": missing,
        "duplicate_matches": duplicate_matches,
        "total": len(ratings),
    }
