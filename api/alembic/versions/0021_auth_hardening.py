"""Add auth hardening tables and account metadata.

Revision ID: 0021_auth_hardening
Revises: 0020_mock_drafts
Create Date: 2026-07-03 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0021_auth_hardening"
down_revision: str | None = "0020_mock_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("users", sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "auth_action_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_type", sa.String(length=50), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_action_tokens_email", "auth_action_tokens", ["email"], unique=False)
    op.create_index("ix_auth_action_tokens_expires_at", "auth_action_tokens", ["expires_at"], unique=False)
    op.create_index("ix_auth_action_tokens_token_hash", "auth_action_tokens", ["token_hash"], unique=True)
    op.create_index("ix_auth_action_tokens_token_type", "auth_action_tokens", ["token_type"], unique=False)
    op.create_index("ix_auth_action_tokens_user_id", "auth_action_tokens", ["user_id"], unique=False)
    op.create_index(
        "ix_auth_action_tokens_user_type_consumed",
        "auth_action_tokens",
        ["user_id", "token_type", "consumed_at"],
        unique=False,
    )

    op.create_table(
        "auth_rate_limit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("identifier_hash", sa.String(length=128), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_rate_limit_events_action", "auth_rate_limit_events", ["action"], unique=False)
    op.create_index(
        "ix_auth_rate_limit_events_action_identifier_created",
        "auth_rate_limit_events",
        ["action", "identifier_hash", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_rate_limit_events_action_ip_created",
        "auth_rate_limit_events",
        ["action", "ip_hash", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_rate_limit_events_created_at",
        "auth_rate_limit_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_rate_limit_events_identifier_hash",
        "auth_rate_limit_events",
        ["identifier_hash"],
        unique=False,
    )
    op.create_index("ix_auth_rate_limit_events_ip_hash", "auth_rate_limit_events", ["ip_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_rate_limit_events_ip_hash", table_name="auth_rate_limit_events")
    op.drop_index("ix_auth_rate_limit_events_identifier_hash", table_name="auth_rate_limit_events")
    op.drop_index("ix_auth_rate_limit_events_created_at", table_name="auth_rate_limit_events")
    op.drop_index("ix_auth_rate_limit_events_action_ip_created", table_name="auth_rate_limit_events")
    op.drop_index("ix_auth_rate_limit_events_action_identifier_created", table_name="auth_rate_limit_events")
    op.drop_index("ix_auth_rate_limit_events_action", table_name="auth_rate_limit_events")
    op.drop_table("auth_rate_limit_events")

    op.drop_index("ix_auth_action_tokens_user_type_consumed", table_name="auth_action_tokens")
    op.drop_index("ix_auth_action_tokens_user_id", table_name="auth_action_tokens")
    op.drop_index("ix_auth_action_tokens_token_type", table_name="auth_action_tokens")
    op.drop_index("ix_auth_action_tokens_token_hash", table_name="auth_action_tokens")
    op.drop_index("ix_auth_action_tokens_expires_at", table_name="auth_action_tokens")
    op.drop_index("ix_auth_action_tokens_email", table_name="auth_action_tokens")
    op.drop_table("auth_action_tokens")

    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "last_failed_login_at")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "email_verified_at")
