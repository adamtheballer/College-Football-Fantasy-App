"""Preserve evidenced pregame chart inputs independently of mutable forecasts.

Revision ID: 0121_player_chart_forecast
Revises: 0120_player_game_history
"""
from alembic import op
import sqlalchemy as sa

revision = "0121_player_chart_forecast"
down_revision = "0120_player_game_history"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "player_chart_forecasts",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("player_id",sa.Integer(),sa.ForeignKey("players.id",ondelete="CASCADE"),nullable=False),
        sa.Column("season",sa.Integer(),nullable=False),
        sa.Column("week",sa.Integer(),nullable=False),
        sa.Column("snapshot_json",sa.JSON(),nullable=False),
        sa.Column("captured_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("player_id","season","week",name="uq_player_chart_forecast"),
    )
    op.create_index("ix_player_chart_forecasts_player_id","player_chart_forecasts",["player_id"])
    op.create_index("ix_player_chart_forecasts_season","player_chart_forecasts",["season"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM player_chart_forecasts)")):
        raise RuntimeError("Pregame chart history exists; roll back application code while retaining history.")
    op.drop_table("player_chart_forecasts")
