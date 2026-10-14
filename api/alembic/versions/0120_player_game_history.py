"""Verified provider per-game player history.
Revision ID: 0120_player_game_history
Revises: 0119_player_chart_history
"""
from alembic import op
import sqlalchemy as sa
revision = "0120_player_game_history"
down_revision = "0119_player_chart_history"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("player_historical_game_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False), sa.Column("season_type", sa.String(30), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.String(length), nullable=False) for name, length in [("provider",64),("provider_player_id",128),("provider_event_id",128),("provider_team_id",128),("team_name",200),("opponent_name",200),("location",30),("result",80),("position",20),("source_response_hash",64),("source_url",500)]],
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False), sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("player_id","season","provider","provider_event_id",name="uq_historical_player_game"),
        sa.CheckConstraint("week >= 0",name="ck_historical_player_game_week"))
    op.create_index("ix_player_historical_game_stats_player_id", "player_historical_game_stats", ["player_id"])

def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM player_historical_game_stats)")):
        raise RuntimeError("Verified game history exists; retain the table when rolling back application code.")
    op.drop_table("player_historical_game_stats")
