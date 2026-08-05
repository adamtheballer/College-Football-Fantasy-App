"""Persist immutable raw ratings separately from current player values.

Revision ID: 0087_player_value_contract
Revises: 0086_content_moderation_events
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0087_player_value_contract"
down_revision = "0086_content_moderation_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Values intentionally remain NULL until the audited reconciliation command
    # runs with a verified backup.  A schema migration must not silently alter
    # beta trade data.
    op.add_column("players", sa.Column("raw_cfb27_rating", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("current_value_rating", sa.Float(), nullable=True))
    op.add_column("players", sa.Column("value_policy_version", sa.String(length=80), nullable=True))
    op.add_column("players", sa.Column("value_calculation_week", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("value_calculated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("players", sa.Column("value_source_batch_id", sa.String(length=120), nullable=True))
    op.add_column("players", sa.Column("value_input_json", sa.JSON(), nullable=True))
    op.create_index("ix_players_raw_cfb27_rating", "players", ["raw_cfb27_rating"])
    op.create_index("ix_players_current_value_rating", "players", ["current_value_rating"])


def downgrade() -> None:
    op.drop_index("ix_players_current_value_rating", table_name="players")
    op.drop_index("ix_players_raw_cfb27_rating", table_name="players")
    op.drop_column("players", "value_input_json")
    op.drop_column("players", "value_source_batch_id")
    op.drop_column("players", "value_calculated_at")
    op.drop_column("players", "value_calculation_week")
    op.drop_column("players", "value_policy_version")
    op.drop_column("players", "current_value_rating")
    op.drop_column("players", "raw_cfb27_rating")
