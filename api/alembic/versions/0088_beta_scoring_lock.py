"""Persist beta scoring snapshots and the post-creation lock.

Revision ID: 0088_beta_scoring_lock
Revises: 0087_player_value_contract
Create Date: 2026-08-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0088_beta_scoring_lock"
down_revision = "0087_player_value_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing leagues retain their present scoring and are not retroactively
    # locked. New beta leagues write an immutable normalized snapshot at create.
    op.add_column("league_settings", sa.Column("scoring_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("league_settings", sa.Column("scoring_locked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("league_settings", "scoring_locked_at")
    op.drop_column("league_settings", "scoring_snapshot_json")
