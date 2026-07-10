"""add provider unmatched resolution fields

Revision ID: 0045_provider_unmatched_resolution
Revises: 0044_player_provider_ids
Create Date: 2026-07-09 00:00:00.000000
"""

from __future__ import annotations

import hashlib

from alembic import op
import sqlalchemy as sa


revision: str = "0045_provider_unmatched_resolution"
down_revision: str | None = "0044_player_provider_ids"
branch_labels: str | None = None
depends_on: str | None = None


def _dedupe_hash(
    *,
    provider: str,
    season: int,
    week: int,
    provider_player_id: str | None,
    provider_player_name: str | None,
    provider_team: str | None,
    reason: str,
) -> str:
    parts = [
        str(provider or "").strip().lower(),
        str(season),
        str(week),
        str(provider_player_id or "").strip().lower(),
        str(provider_player_name or "").strip().lower(),
        str(provider_team or "").strip().lower(),
        str(reason or "").strip().lower(),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.add_column("provider_unmatched_player_rows", sa.Column("dedupe_hash", sa.String(length=64), nullable=True))
    op.add_column("provider_unmatched_player_rows", sa.Column("mapped_player_id", sa.Integer(), nullable=True))
    op.add_column("provider_unmatched_player_rows", sa.Column("resolved_by_user_id", sa.Integer(), nullable=True))
    op.add_column("provider_unmatched_player_rows", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_provider_unmatched_rows_mapped_player_id",
        "provider_unmatched_player_rows",
        "players",
        ["mapped_player_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_provider_unmatched_rows_resolved_by_user_id",
        "provider_unmatched_player_rows",
        "users",
        ["resolved_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, provider, season, week, provider_player_id, provider_player_name, provider_team, reason
            FROM provider_unmatched_player_rows
            WHERE dedupe_hash IS NULL
            ORDER BY id ASC
            """
        )
    ).fetchall()
    seen: set[str] = set()
    for row in rows:
        row_id, provider, season, week, provider_player_id, provider_player_name, provider_team, reason = row
        dedupe_hash = _dedupe_hash(
            provider=provider,
            season=season,
            week=week,
            provider_player_id=provider_player_id,
            provider_player_name=provider_player_name,
            provider_team=provider_team,
            reason=reason,
        )
        if dedupe_hash in seen:
            dedupe_hash = hashlib.sha256(f"{dedupe_hash}|legacy-row:{row_id}".encode("utf-8")).hexdigest()
        seen.add(dedupe_hash)
        bind.execute(
            sa.text(
                """
                UPDATE provider_unmatched_player_rows
                SET dedupe_hash = :dedupe_hash
                WHERE id = :row_id
                """
            ),
            {"dedupe_hash": dedupe_hash, "row_id": row_id},
        )

    op.create_index(
        "ix_provider_unmatched_rows_dedupe_hash",
        "provider_unmatched_player_rows",
        ["dedupe_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_unmatched_rows_dedupe_hash", table_name="provider_unmatched_player_rows")
    op.drop_constraint(
        "fk_provider_unmatched_rows_resolved_by_user_id",
        "provider_unmatched_player_rows",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_provider_unmatched_rows_mapped_player_id",
        "provider_unmatched_player_rows",
        type_="foreignkey",
    )
    op.drop_column("provider_unmatched_player_rows", "resolved_at")
    op.drop_column("provider_unmatched_player_rows", "resolved_by_user_id")
    op.drop_column("provider_unmatched_player_rows", "mapped_player_id")
    op.drop_column("provider_unmatched_player_rows", "dedupe_hash")
