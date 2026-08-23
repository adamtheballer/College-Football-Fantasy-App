"""Enforce a durable cooldown between manager-name changes.

Revision ID: 0106_manager_name_cooldown
Revises: 0105_auth_token_ts_defaults
"""

import sqlalchemy as sa
from alembic import op


revision = "0106_manager_name_cooldown"
down_revision = "0105_auth_token_ts_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("manager_name_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "manager_name_changed_at")
