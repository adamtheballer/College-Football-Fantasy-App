"""Persist finalized chart facts, publication coverage and value input context.
Revision ID: 0119_player_chart_history
Revises: 0118_native_push_delivery
"""
from alembic import op
import sqlalchemy as sa
revision = "0119_player_chart_history"
down_revision = "0118_native_push_delivery"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("player_trade_values", sa.Column("input_context_json", sa.JSON(), nullable=True))
    timestamps = lambda: [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]
    op.create_table("player_chart_weeks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False), sa.Column("season", sa.Integer(), nullable=False), sa.Column("week", sa.Integer(), nullable=False), sa.Column("stats_json", sa.JSON(), nullable=False), sa.Column("standard_points", sa.Float(), nullable=False), sa.Column("scoring_rules_json", sa.JSON(), nullable=False), sa.Column("input_hash", sa.String(64), nullable=False), sa.Column("source_stat_id", sa.Integer(), sa.ForeignKey("player_stats.id", ondelete="SET NULL"), nullable=True), sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False), sa.Column("calculation_version", sa.String(80), nullable=False), *timestamps(), sa.UniqueConstraint("player_id", "season", "week", name="uq_player_chart_week"))
    op.create_index("ix_player_chart_weeks_player_id", "player_chart_weeks", ["player_id"])
    op.create_index("ix_player_chart_weeks_season", "player_chart_weeks", ["season"])
    op.create_table("player_chart_publication_runs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("season", sa.Integer(), nullable=False), sa.Column("week", sa.Integer(), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("coverage_json", sa.JSON(), nullable=False), *timestamps())
    op.create_index("ix_player_chart_publication_runs_season", "player_chart_publication_runs", ["season"])

def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM player_chart_weeks)")):
        raise RuntimeError("Finalized chart history exists; roll back application code while retaining history.")
    op.drop_table("player_chart_publication_runs")
    op.drop_table("player_chart_weeks")
    op.drop_column("player_trade_values", "input_context_json")
