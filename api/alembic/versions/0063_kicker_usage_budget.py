"""Add explicit kicking opportunity shares to the audited usage budget.

Revision ID: 0063_kicker_usage_budget
Revises: 0062_quarantine_legacy_proj
"""

import sqlalchemy as sa
from alembic import op


revision = "0063_kicker_usage_budget"
down_revision = "0062_quarantine_legacy_proj"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usage_shares", sa.Column("kicker_share", sa.Float(), nullable=False, server_default="0"))
    op.add_column("usage_shares", sa.Column("prior_kicker_share", sa.Float(), nullable=False, server_default="0"))
    op.add_column("usage_shares", sa.Column("projected_kicker_share", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("usage_shares", "projected_kicker_share")
    op.drop_column("usage_shares", "prior_kicker_share")
    op.drop_column("usage_shares", "kicker_share")
