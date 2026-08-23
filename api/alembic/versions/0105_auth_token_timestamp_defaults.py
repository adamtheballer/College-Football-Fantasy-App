"""Repair timestamp defaults for durable authentication-action tokens.

Revision ID: 0105_auth_token_timestamp_defaults
Revises: 0104_secure_password_reset
"""

import sqlalchemy as sa
from alembic import op


revision = "0105_auth_token_timestamp_defaults"
down_revision = "0104_secure_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0021 created these NOT NULL columns without server defaults, unlike the
    # model's TimestampMixin. Repair existing databases without rewriting rows.
    op.alter_column("auth_action_tokens", "created_at", server_default=sa.text("now()"))
    op.alter_column("auth_action_tokens", "updated_at", server_default=sa.text("now()"))


def downgrade() -> None:
    op.alter_column("auth_action_tokens", "updated_at", server_default=None)
    op.alter_column("auth_action_tokens", "created_at", server_default=None)
