"""add beta early-access reservations

Revision ID: 0083_beta_access
Revises: 0082_release_audit_timestamps
"""

from alembic import op
import sqlalchemy as sa


revision = "0083_beta_access"
down_revision = "0082_release_audit_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("beta_access_granted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "beta_access_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_waitlist_id", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("code_hmac", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="AVAILABLE"),
        sa.Column("source_status", sa.String(length=32), nullable=False, server_default="READY_SENT"),
        sa.Column("source_waitlist_status", sa.String(length=64), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column("access_code_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_delivery_status", sa.String(length=32), nullable=True),
        sa.Column("email_delivery_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_delivery_provider_id", sa.String(length=255), nullable=True),
        sa.Column("email_delivery_attempt_count", sa.Integer(), nullable=True),
        sa.Column("email_delivery_last_error", sa.Text(), nullable=True),
        sa.Column("manual_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reservation_nonce_hmac", sa.String(length=128), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("source_waitlist_id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("code_hmac"),
        sa.UniqueConstraint("redeemed_user_id"),
    )
    op.create_index("ix_beta_access_codes_source_waitlist_id", "beta_access_codes", ["source_waitlist_id"])
    op.create_index("ix_beta_access_codes_email", "beta_access_codes", ["email"])
    op.create_index("ix_beta_access_codes_code_hmac", "beta_access_codes", ["code_hmac"])
    op.create_index("ix_beta_access_codes_redeemed_user_id", "beta_access_codes", ["redeemed_user_id"])
    op.create_index("ix_beta_access_codes_state_expires", "beta_access_codes", ["state", "reservation_expires_at"])
    op.create_index("ix_beta_access_codes_source_status", "beta_access_codes", ["source_status"])
    op.create_table(
        "beta_access_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("beta_access_code_id", sa.Integer(), sa.ForeignKey("beta_access_codes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("email_hmac", sa.String(length=128), nullable=True),
        sa.Column("code_hmac", sa.String(length=128), nullable=True),
        sa.Column("ip_hmac", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_beta_access_audit_events_beta_access_code_id", "beta_access_audit_events", ["beta_access_code_id"])
    op.create_index("ix_beta_access_audit_events_code_created", "beta_access_audit_events", ["beta_access_code_id", "created_at"])
    op.create_index("ix_beta_access_audit_events_action_created", "beta_access_audit_events", ["action", "created_at"])


def downgrade() -> None:
    op.drop_table("beta_access_audit_events")
    op.drop_table("beta_access_codes")
    op.drop_column("users", "beta_access_granted_at")
