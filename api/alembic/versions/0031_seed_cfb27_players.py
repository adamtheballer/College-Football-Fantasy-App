"""seed cfb27 player pool

Revision ID: 0031_seed_cfb27_players
Revises: 0030_align_timestamp_nullability
Create Date: 2026-07-14 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
import re

import sqlalchemy as sa
from alembic import op


revision: str = "0031_seed_cfb27_players"
down_revision: str | None = "0030_align_timestamp_nullability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CFB27_EXTERNAL_PREFIX = "cfb27:"
CFB27_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
CFB27_SOURCE_PATH = Path(__file__).resolve().parents[2] / "app" / "data" / "cfb27_ratings.json"


def _normalize_identity_text(value: str | None) -> str:
    normalized = (value or "").lower().replace("&", "and")
    normalized = re.sub(r"\b(jr|jr\.|iii|ii|iv)\b", "", normalized)
    return re.sub(r"[^a-z0-9]+", "", normalized).strip()


def _identity_key(*, name: str | None, school: str | None, position: str | None) -> str:
    return "|".join(
        [
            _normalize_identity_text(name),
            _normalize_identity_text(school),
            (position or "").strip().upper(),
        ]
    )


def _load_cfb27_rows() -> list[dict[str, object]]:
    source = json.loads(CFB27_SOURCE_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for row in source:
        rows.append(
            {
                "rank": int(row["rank"]),
                "name": str(row["name"]),
                "school": str(row["school"]),
                "position": str(row["position"]).strip().upper(),
                "overall": int(row["overall"]),
            }
        )
    return rows


def _has_rank(row: sa.Row) -> bool:
    sheet_adp = row._mapping.get("sheet_adp")
    return sheet_adp is not None and float(sheet_adp) > 0


def _canonical_player(rows: list[sa.Row]) -> sa.Row:
    return sorted(rows, key=lambda row: (0 if _has_rank(row) else 1, int(row._mapping["id"])))[0]


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text(
            """
            select id, name, school, position, sheet_adp
            from players
            where position in ('QB', 'RB', 'WR', 'TE', 'K')
              and lower(coalesce(name, '')) not like 'test %'
              and lower(coalesce(name, '')) not like 'smoke %'
            """
        )
    ).all()
    players_by_key: dict[str, list[sa.Row]] = {}
    for player in existing:
        key = _identity_key(
            name=player._mapping["name"],
            school=player._mapping["school"],
            position=player._mapping["position"],
        )
        players_by_key.setdefault(key, []).append(player)

    for rating in _load_cfb27_rows():
        key = _identity_key(
            name=str(rating["name"]),
            school=str(rating["school"]),
            position=str(rating["position"]),
        )
        external_id = f"{CFB27_EXTERNAL_PREFIX}{key}"
        candidates = players_by_key.get(key)
        if candidates:
            canonical = _canonical_player(candidates)
            bind.execute(
                sa.text(
                    """
                    update players
                    set name = :name,
                        school = :school,
                        position = :position,
                        external_id = coalesce(nullif(external_id, ''), :external_id),
                        updated_at = now()
                    where id = :id
                    """
                ),
                {
                    "id": canonical._mapping["id"],
                    "name": rating["name"],
                    "school": rating["school"],
                    "position": rating["position"],
                    "external_id": external_id,
                },
            )
            continue

        result = bind.execute(
            sa.text(
                """
                insert into players (
                    external_id,
                    name,
                    position,
                    school,
                    created_at,
                    updated_at
                )
                values (
                    :external_id,
                    :name,
                    :position,
                    :school,
                    now(),
                    now()
                )
                returning id, name, school, position, sheet_adp
                """
            ),
            {
                "external_id": external_id,
                "name": rating["name"],
                "position": rating["position"],
                "school": rating["school"],
            },
        )
        inserted = result.one()
        players_by_key[key] = [inserted]


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            delete from players
            where external_id like :external_id_prefix
              and id not in (select player_id from roster_entries where player_id is not null)
              and id not in (select player_id from draft_picks where player_id is not null)
              and id not in (select player_id from watchlist_players where player_id is not null)
              and id not in (select player_id from trade_offer_items where player_id is not null)
              and id not in (select add_player_id from waiver_claims where add_player_id is not null)
              and id not in (select drop_player_id from waiver_claims where drop_player_id is not null)
            """
        ),
        {
            "external_id_prefix": f"{CFB27_EXTERNAL_PREFIX}%",
        },
    )
