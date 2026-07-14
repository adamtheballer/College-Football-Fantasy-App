"""add cfb27 player fields

Revision ID: 0032_add_cfb27_player_fields
Revises: 0031_seed_cfb27_players
Create Date: 2026-07-14 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
import re

import sqlalchemy as sa
from alembic import op


revision: str = "0032_add_cfb27_player_fields"
down_revision: str | None = "0031_seed_cfb27_players"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CFB27_SOURCE_ID = "cfb27"
CFB27_EXTERNAL_PREFIX = "cfb27:"
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
    rows = [
        {
            "source_order": index,
            "position_rank": int(row["rank"]),
            "name": str(row["name"]),
            "school": str(row["school"]),
            "position": str(row["position"]).strip().upper(),
            "overall": int(row["overall"]),
        }
        for index, row in enumerate(source)
    ]
    global_rank_by_key = {
        _identity_key(name=row["name"], school=row["school"], position=row["position"]): index + 1
        for index, row in enumerate(
            sorted(rows, key=lambda row: (-int(row["overall"]), int(row["source_order"])))
        )
    }
    for row in rows:
        row["rank"] = global_rank_by_key[
            _identity_key(name=str(row["name"]), school=str(row["school"]), position=str(row["position"]))
        ]
    return rows


def _has_rank(row: sa.Row) -> bool:
    sheet_adp = row._mapping.get("sheet_adp")
    return sheet_adp is not None and float(sheet_adp) > 0


def _canonical_player(rows: list[sa.Row]) -> sa.Row:
    return sorted(rows, key=lambda row: (0 if _has_rank(row) else 1, int(row._mapping["id"])))[0]


def upgrade() -> None:
    op.add_column("players", sa.Column("cfb27_rank", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("cfb27_overall", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("cfb27_position_rank", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("cfb27_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_players_cfb27_rank", "players", ["cfb27_rank"])
    op.create_index("ix_players_cfb27_overall", "players", ["cfb27_overall"])

    bind = op.get_bind()
    existing = bind.execute(
        sa.text(
            """
            select id, name, school, position, sheet_adp, external_id, sheet_source_sheet_id
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
        candidates = players_by_key.get(key)
        if not candidates:
            continue

        canonical = _canonical_player(candidates)
        sheet_adp = canonical._mapping["sheet_adp"]
        should_clear_cfb27_sheet_adp = (
            canonical._mapping["external_id"]
            and str(canonical._mapping["external_id"]).startswith(CFB27_EXTERNAL_PREFIX)
            and canonical._mapping["sheet_source_sheet_id"] == CFB27_SOURCE_ID
            and sheet_adp is not None
            and float(sheet_adp) == float(rating["position_rank"])
        )
        bind.execute(
            sa.text(
                """
                update players
                set cfb27_rank = :cfb27_rank,
                    cfb27_overall = :cfb27_overall,
                    cfb27_position_rank = :cfb27_position_rank,
                    cfb27_synced_at = now(),
                    sheet_adp = case when :clear_sheet_adp then null else sheet_adp end,
                    sheet_source_sheet_id = case
                        when :clear_sheet_adp and sheet_source_sheet_id = :source_id then null
                        else sheet_source_sheet_id
                    end,
                    updated_at = now()
                where id = :id
                """
            ),
            {
                "id": canonical._mapping["id"],
                "cfb27_rank": int(rating["rank"]),
                "cfb27_overall": int(rating["overall"]),
                "cfb27_position_rank": int(rating["position_rank"]),
                "clear_sheet_adp": should_clear_cfb27_sheet_adp,
                "source_id": CFB27_SOURCE_ID,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_players_cfb27_overall", table_name="players")
    op.drop_index("ix_players_cfb27_rank", table_name="players")
    op.drop_column("players", "cfb27_synced_at")
    op.drop_column("players", "cfb27_position_rank")
    op.drop_column("players", "cfb27_overall")
    op.drop_column("players", "cfb27_rank")
