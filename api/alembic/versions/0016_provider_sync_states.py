"""add provider sync states

Revision ID: 0016_provider_sync_states
Revises: 0015_refresh_sessions
Create Date: 2026-04-02 21:58:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0016_provider_sync_states"
down_revision: str | None = "0015_refresh_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_sync_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("feed", sa.String(length=128), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="idle"),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "feed", "scope_key", name="uq_provider_sync_states_provider_feed_scope"),
    )
    op.create_index(
        "ix_provider_sync_states_provider_feed",
        "provider_sync_states",
        ["provider", "feed"],
        unique=False,
    )
    op.create_index("ix_provider_sync_states_scope_key", "provider_sync_states", ["scope_key"], unique=False)
    op.create_index("ix_provider_sync_states_expires_at", "provider_sync_states", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_provider_sync_states_expires_at", table_name="provider_sync_states")
    op.drop_index("ix_provider_sync_states_scope_key", table_name="provider_sync_states")
    op.drop_index("ix_provider_sync_states_provider_feed", table_name="provider_sync_states")
    op.drop_table("provider_sync_states")
