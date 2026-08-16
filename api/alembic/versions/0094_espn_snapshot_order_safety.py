"""Persist ESPN captured-versus-accepted snapshot ordering evidence.

Revision ID: 0094_espn_snapshot_order_safety
Revises: 0093_legacy_kicker_scoring_audit
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0094_espn_snapshot_order_safety"
down_revision: str | None = "0093_legacy_kicker_scoring_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("provider_game_polls", sa.Column("accepted_snapshot_hash", sa.String(length=64), nullable=True))
    op.add_column("provider_game_polls", sa.Column("last_captured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("provider_game_polls", sa.Column("last_snapshot_classification", sa.String(length=32), nullable=True))
    for column in (
        "accepted_snapshot_count",
        "duplicate_snapshot_count",
        "stale_snapshot_count",
        "ambiguous_snapshot_count",
        "pending_final_correction_count",
    ):
        op.add_column("provider_game_polls", sa.Column(column, sa.Integer(), nullable=False, server_default="0"))

    op.add_column("provider_game_snapshots", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.add_column("provider_game_snapshots", sa.Column("provider_revision", sa.String(length=128), nullable=True))
    op.add_column("provider_game_snapshots", sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("provider_game_snapshots", sa.Column("provider_etag", sa.String(length=512), nullable=True))
    op.add_column("provider_game_snapshots", sa.Column("response_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("provider_game_snapshots", sa.Column("event_period", sa.Integer(), nullable=True))
    op.add_column("provider_game_snapshots", sa.Column("event_clock", sa.String(length=32), nullable=True))
    op.add_column("provider_game_snapshots", sa.Column("event_state", sa.String(length=32), nullable=True))
    op.add_column("provider_game_snapshots", sa.Column("classification", sa.String(length=32), nullable=False, server_default="NEWER"))
    op.add_column("provider_game_snapshots", sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("provider_game_snapshots", sa.Column("rejection_reason", sa.String(length=500), nullable=True))

    # Existing rows were the branch's previously accepted canonical state.
    # Preserve that state explicitly before new rejected captures arrive.
    op.execute(
        """
        UPDATE provider_game_polls
        SET accepted_snapshot_hash = latest_snapshot_hash,
            accepted_snapshot_count = CASE WHEN latest_snapshot_hash IS NULL THEN 0 ELSE 1 END
        WHERE latest_snapshot_hash IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE provider_game_snapshots snapshot
        SET accepted = true
        FROM provider_game_polls poll
        WHERE snapshot.provider = poll.provider
          AND snapshot.provider_game_id = poll.provider_game_id
          AND snapshot.snapshot_hash = poll.latest_snapshot_hash
        """
    )

    # Hash equality identifies content, not ordering.  Captures are retained
    # individually so an operator can audit duplicates, stale responses, and
    # ambiguous provider responses rather than only the latest payload.
    op.drop_constraint("uq_provider_game_snapshots_provider_game_hash", "provider_game_snapshots", type_="unique")
    op.create_index(
        "ix_provider_game_snapshots_game_hash",
        "provider_game_snapshots",
        ["provider", "provider_game_id", "snapshot_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_game_snapshots_game_hash", table_name="provider_game_snapshots")
    # The prior schema deduplicated identical payload hashes.  A rollback must
    # collapse only the newer per-capture audit duplicates before restoring
    # that historical constraint.
    op.execute(
        """
        DELETE FROM provider_game_snapshots discard
        USING provider_game_snapshots keep
        WHERE discard.provider = keep.provider
          AND discard.provider_game_id = keep.provider_game_id
          AND discard.snapshot_hash = keep.snapshot_hash
          AND discard.id > keep.id
        """
    )
    op.create_unique_constraint(
        "uq_provider_game_snapshots_provider_game_hash",
        "provider_game_snapshots",
        ["provider", "provider_game_id", "snapshot_hash"],
    )
    for column in (
        "rejection_reason",
        "accepted",
        "classification",
        "event_state",
        "event_clock",
        "event_period",
        "response_metadata",
        "provider_etag",
        "provider_updated_at",
        "provider_revision",
        "captured_at",
    ):
        op.drop_column("provider_game_snapshots", column)
    for column in (
        "pending_final_correction_count",
        "ambiguous_snapshot_count",
        "stale_snapshot_count",
        "duplicate_snapshot_count",
        "accepted_snapshot_count",
        "last_snapshot_classification",
        "last_captured_at",
        "accepted_snapshot_hash",
    ):
        op.drop_column("provider_game_polls", column)
