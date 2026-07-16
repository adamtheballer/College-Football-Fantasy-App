"""Restore team-week score compatibility fields removed by reconciliation.

Revision ID: 0041_score_compat
Revises: 0040_reconcile_active_schema
Create Date: 2026-07-15 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0041_score_compat"
down_revision: str | None = "0040_reconcile_active_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    columns = _columns("team_week_scores")
    for name, source in (
        ("points_total", "total_points"),
        ("points_starters", "starter_points"),
        ("points_bench", "bench_points"),
    ):
        if name not in columns:
            op.add_column("team_week_scores", sa.Column(name, sa.Float(), nullable=True))
        op.execute(f"UPDATE team_week_scores SET {name} = COALESCE({name}, {source}, 0)")
        with op.batch_alter_table("team_week_scores") as batch:
            batch.alter_column(name, existing_type=sa.Float(), nullable=False)

    with op.batch_alter_table("lineup_week_snapshots") as batch:
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    if "ix_drafts_live_state" in _indexes("drafts"):
        op.drop_index("ix_drafts_live_state", table_name="drafts")


def downgrade() -> None:
    raise NotImplementedError("Compatibility fields are required by the current scoring model.")
