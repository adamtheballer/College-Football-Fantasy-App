"""Add durable ESPN per-game shadow polling state.

Revision ID: 0092_espn_shadow_game_polls
Revises: 0091_durable_notification_outbox
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0092_espn_shadow_game_polls"
down_revision: str | None = "0091_durable_notification_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_game_polls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_game_id", sa.String(length=128), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="scheduled"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("latest_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("latest_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        # TimestampMixin is non-nullable in the runtime metadata.  Keep this
        # unreleased migration exact so `alembic check` protects the shadow
        # worker contract instead of reporting false schema drift.
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_game_id", name="uq_provider_game_polls_provider_game"),
    )
    op.create_index("ix_provider_game_polls_due", "provider_game_polls", ["provider", "next_poll_at", "lease_expires_at"])
    op.create_index("ix_provider_game_polls_season_week", "provider_game_polls", ["provider", "season", "week"])
    op.create_index("ix_provider_game_polls_status", "provider_game_polls", ["provider", "status"])

    op.create_table(
        "provider_game_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_game_id", sa.String(length=128), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("normalized_rows", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_game_id", "snapshot_hash", name="uq_provider_game_snapshots_provider_game_hash"
        ),
    )
    op.create_index("ix_provider_game_snapshots_game", "provider_game_snapshots", ["provider", "provider_game_id", "provider_as_of"])
    op.create_index("ix_provider_game_snapshots_season_week", "provider_game_snapshots", ["provider", "season", "week"])


def downgrade() -> None:
    op.drop_index("ix_provider_game_snapshots_season_week", table_name="provider_game_snapshots")
    op.drop_index("ix_provider_game_snapshots_game", table_name="provider_game_snapshots")
    op.drop_table("provider_game_snapshots")
    op.drop_index("ix_provider_game_polls_status", table_name="provider_game_polls")
    op.drop_index("ix_provider_game_polls_season_week", table_name="provider_game_polls")
    op.drop_index("ix_provider_game_polls_due", table_name="provider_game_polls")
    op.drop_table("provider_game_polls")
