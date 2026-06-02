"""add sheet projection fields on players

Revision ID: 0018_sheet_projection_fields
Revises: 0017_cfb_standing_snapshots
Create Date: 2026-05-25 14:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0018_sheet_projection_fields"
down_revision: str | None = "0017_cfb_standing_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("players", sa.Column("player_class", sa.String(length=30), nullable=True))
    op.add_column("players", sa.Column("sheet_adp", sa.Float(), nullable=True))
    op.add_column("players", sa.Column("sheet_projected_season_points", sa.Float(), nullable=True))
    op.add_column("players", sa.Column("sheet_source_sheet_id", sa.String(length=200), nullable=True))
    op.add_column("players", sa.Column("sheet_synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "sheet_synced_at")
    op.drop_column("players", "sheet_source_sheet_id")
    op.drop_column("players", "sheet_projected_season_points")
    op.drop_column("players", "sheet_adp")
    op.drop_column("players", "player_class")
