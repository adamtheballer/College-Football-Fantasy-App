"""add persisted player season outlooks

Revision ID: 0095_player_season_outlooks
Revises: 0094_espn_snapshot_order_safety
"""

from alembic import op
import sqlalchemy as sa


revision = "0095_player_season_outlooks"
down_revision = "0094_espn_snapshot_order_safety"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_season_outlooks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("outlook_type", sa.String(length=30), nullable=False, server_default="PRESEASON"),
        sa.Column("generator_version", sa.String(length=80), nullable=False),
        sa.Column("facts_version", sa.String(length=80), nullable=False),
        sa.Column("facts_json", sa.JSON(), nullable=False),
        sa.Column("outlook_text", sa.Text(), nullable=True),
        sa.Column("outlook_status", sa.String(length=40), nullable=False),
        sa.Column("historical_source_batch_id", sa.Integer(), nullable=True),
        sa.Column("projection_source_batch_id", sa.String(length=200), nullable=True),
        sa.Column("identity_source_batch_id", sa.String(length=200), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="AUTO_APPROVED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "season_year",
            "outlook_type",
            "generator_version",
            name="uq_player_season_outlooks_identity",
        ),
    )
    op.create_index("ix_player_season_outlooks_player_season", "player_season_outlooks", ["player_id", "season_year"])
    op.create_index("ix_player_season_outlooks_season_status", "player_season_outlooks", ["season_year", "outlook_status"])


def downgrade() -> None:
    op.drop_index("ix_player_season_outlooks_season_status", table_name="player_season_outlooks")
    op.drop_index("ix_player_season_outlooks_player_season", table_name="player_season_outlooks")
    op.drop_table("player_season_outlooks")
