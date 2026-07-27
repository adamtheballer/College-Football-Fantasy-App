"""add canonical player trade values

Revision ID: 0079_player_trade_values
Revises: 0078_league_player_events
"""

from alembic import op
import sqlalchemy as sa

revision = "0079_player_trade_values"
down_revision = "0078_league_player_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_trade_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False), sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False), sa.Column("tier", sa.String(length=30), nullable=False),
        sa.Column("positional_value_rank", sa.Integer()), sa.Column("weekly_change", sa.Float()),
        sa.Column("confidence", sa.Float(), nullable=False), sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("input_version", sa.String(length=80), nullable=False),
        sa.Column("explanation_json", sa.JSON()), sa.Column("factor_breakdown_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("player_id", "season", "week", "policy_version", name="uq_player_trade_values_player_week_policy"),
    )
    op.create_index("ix_player_trade_values_player_season", "player_trade_values", ["player_id", "season"])
    op.create_index("ix_player_trade_values_season_week", "player_trade_values", ["season", "week"])


def downgrade() -> None:
    op.drop_table("player_trade_values")
