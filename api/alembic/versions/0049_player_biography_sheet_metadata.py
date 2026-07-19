"""Add player biography import provenance and depth-chart fields."""

from alembic import op
import sqlalchemy as sa


revision = "0049_player_bio_metadata"
down_revision = "0048_espn_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("depth_chart_position", sa.String(length=20), nullable=True))
    op.add_column("players", sa.Column("depth_order", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("bio_source", sa.String(length=80), nullable=True))
    op.add_column("players", sa.Column("bio_source_sheet_id", sa.String(length=80), nullable=True))
    op.add_column("players", sa.Column("bio_source_row", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("bio_imported_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "bio_imported_at")
    op.drop_column("players", "bio_source_row")
    op.drop_column("players", "bio_source_sheet_id")
    op.drop_column("players", "bio_source")
    op.drop_column("players", "depth_order")
    op.drop_column("players", "depth_chart_position")
