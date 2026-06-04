"""player stats

Revision ID: 0002_player_stats
Revises: 0001_initial
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_player_stats"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="sportsdata"),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_player_stats_player_season_week"),
    )
    op.create_index("ix_player_stats_player_id", "player_stats", ["player_id"])
    op.create_index("ix_player_stats_season_week", "player_stats", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_player_stats_season_week", table_name="player_stats")
    op.drop_index("ix_player_stats_player_id", table_name="player_stats")
    op.drop_table("player_stats")
