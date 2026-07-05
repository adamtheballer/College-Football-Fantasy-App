"""add sheet ranking and projection fields on players

Revision ID: 0018_sheet_projection_fields
Revises: 0017_cfb_standing_snapshots
Create Date: 2026-06-17 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0018_sheet_projection_fields"
down_revision: str | None = "0017_cfb_standing_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("players")}


def upgrade() -> None:
    existing = _existing_columns()
    columns = [
        ("player_class", sa.Column("player_class", sa.String(length=30), nullable=True)),
        ("sheet_adp", sa.Column("sheet_adp", sa.Float(), nullable=True)),
        ("sheet_projected_season_points", sa.Column("sheet_projected_season_points", sa.Float(), nullable=True)),
        ("sheet_projection_stats", sa.Column("sheet_projection_stats", sa.JSON(), nullable=True)),
        ("sheet_source_sheet_id", sa.Column("sheet_source_sheet_id", sa.String(length=200), nullable=True)),
        ("sheet_synced_at", sa.Column("sheet_synced_at", sa.DateTime(timezone=True), nullable=True)),
    ]
    for name, column in columns:
        if name not in existing:
            op.add_column("players", column)


def downgrade() -> None:
    existing = _existing_columns()
    for name in (
        "sheet_synced_at",
        "sheet_source_sheet_id",
        "sheet_projection_stats",
        "sheet_projected_season_points",
        "sheet_adp",
        "player_class",
    ):
        if name in existing:
            op.drop_column("players", name)
