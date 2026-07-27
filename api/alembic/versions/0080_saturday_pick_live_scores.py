"""persist Saturday Pick 6 live scoring snapshots

Revision ID: 0080_saturday_pick_live_scores
Revises: 0079_player_trade_values
"""

from alembic import op
import sqlalchemy as sa


revision = "0080_saturday_pick_live_scores"
down_revision = "0079_player_trade_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("saturday_pick_players", sa.Column("live_points", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("saturday_pick_players", "live_points")
