"""Add published position-only player fantasy rankings.

Revision ID: 0057_player_season_ranks
Revises: 0056_waiver_pending_claims
"""

from alembic import op
import sqlalchemy as sa


revision = "0057_player_season_ranks"
down_revision = "0056_waiver_pending_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_season_ranks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("through_week", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column("fantasy_points", sa.Float(), nullable=False),
        sa.Column("position_rank", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "season", "through_week", name="uq_player_season_rank_snapshot"),
    )
    op.create_index("ix_player_season_ranks_player_season", "player_season_ranks", ["player_id", "season"])
    op.create_index("ix_player_season_ranks_season_week_position_rank", "player_season_ranks", ["season", "through_week", "position", "position_rank"])


def downgrade() -> None:
    op.drop_index("ix_player_season_ranks_season_week_position_rank", table_name="player_season_ranks")
    op.drop_index("ix_player_season_ranks_player_season", table_name="player_season_ranks")
    op.drop_table("player_season_ranks")
