"""Add durable, single-use password-reset state and security email outbox.

Revision ID: 0104_secure_password_reset
Revises: 0103_sunday_waivers
"""

import sqlalchemy as sa
from alembic import op


revision = "0104_secure_password_reset"
down_revision = "0103_sunday_waivers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_action_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_action_tokens", sa.Column("revoke_reason", sa.String(length=80), nullable=True))
    op.add_column("auth_action_tokens", sa.Column("request_id", sa.String(length=96), nullable=True))
    op.add_column("auth_action_tokens", sa.Column("completed_ip_hash", sa.String(length=128), nullable=True))
    op.add_column("auth_action_tokens", sa.Column("completed_user_agent_hash", sa.String(length=128), nullable=True))
    op.create_unique_constraint("uq_auth_action_tokens_request_id", "auth_action_tokens", ["request_id"])
    op.create_index("ix_auth_action_tokens_user_type_revoked", "auth_action_tokens", ["user_id", "token_type", "revoked_at"])

    op.create_table(
        "security_email_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("auth_action_token_id", sa.Integer(), sa.ForeignKey("auth_action_tokens.id", ondelete="CASCADE"), nullable=True),
        sa.Column("message_type", sa.String(length=60), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False, unique=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_security_email_outbox_status_due", "security_email_outbox", ["status", "next_attempt_at"])
    op.create_index("ix_security_email_outbox_user_id", "security_email_outbox", ["user_id"])
    op.create_index("ix_security_email_outbox_token_id", "security_email_outbox", ["auth_action_token_id"])

    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("request_id", sa.String(length=96), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=128), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_security_audit_events_user_type_created", "security_audit_events", ["user_id", "event_type", "created_at"])
    op.create_index("ix_security_audit_events_request_id", "security_audit_events", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_security_audit_events_request_id", table_name="security_audit_events")
    op.drop_index("ix_security_audit_events_user_type_created", table_name="security_audit_events")
    op.drop_table("security_audit_events")
    op.drop_index("ix_security_email_outbox_token_id", table_name="security_email_outbox")
    op.drop_index("ix_security_email_outbox_user_id", table_name="security_email_outbox")
    op.drop_index("ix_security_email_outbox_status_due", table_name="security_email_outbox")
    op.drop_table("security_email_outbox")
    op.drop_index("ix_auth_action_tokens_user_type_revoked", table_name="auth_action_tokens")
    op.drop_constraint("uq_auth_action_tokens_request_id", "auth_action_tokens", type_="unique")
    op.drop_column("auth_action_tokens", "completed_user_agent_hash")
    op.drop_column("auth_action_tokens", "completed_ip_hash")
    op.drop_column("auth_action_tokens", "request_id")
    op.drop_column("auth_action_tokens", "revoke_reason")
    op.drop_column("auth_action_tokens", "revoked_at")
