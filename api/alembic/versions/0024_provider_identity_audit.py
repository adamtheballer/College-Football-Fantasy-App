"""Add provider identity audit tables.

Revision ID: 0024_provider_identity_audit
Revises: 0023_scoring_worker_reliability
Create Date: 2026-07-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0024_provider_identity_audit"
down_revision: str | None = "0023_scoring_worker_reliability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_unmatched_player_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("provider_player_id", sa.String(length=120), nullable=True),
        sa.Column("provider_player_name", sa.String(length=200), nullable=True),
        sa.Column("provider_team", sa.String(length=200), nullable=True),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="open", nullable=False),
        sa.Column("raw_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_unmatched_rows_provider_week",
        "provider_unmatched_player_rows",
        ["provider", "season", "week"],
    )
    op.create_index("ix_provider_unmatched_rows_status", "provider_unmatched_player_rows", ["status"])

    op.create_table(
        "provider_player_identity_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("provider_player_id", sa.String(length=120), nullable=True),
        sa.Column("provider_player_name", sa.String(length=200), nullable=True),
        sa.Column("provider_team", sa.String(length=200), nullable=True),
        sa.Column("match_type", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("raw_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_identity_audits_provider_week",
        "provider_player_identity_audits",
        ["provider", "season", "week"],
    )
    op.create_index("ix_provider_identity_audits_match_type", "provider_player_identity_audits", ["match_type"])
    op.create_index("ix_provider_identity_audits_player_id", "provider_player_identity_audits", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_provider_identity_audits_player_id", table_name="provider_player_identity_audits")
    op.drop_index("ix_provider_identity_audits_match_type", table_name="provider_player_identity_audits")
    op.drop_index("ix_provider_identity_audits_provider_week", table_name="provider_player_identity_audits")
    op.drop_table("provider_player_identity_audits")

    op.drop_index("ix_provider_unmatched_rows_status", table_name="provider_unmatched_player_rows")
    op.drop_index("ix_provider_unmatched_rows_provider_week", table_name="provider_unmatched_player_rows")
    op.drop_table("provider_unmatched_player_rows")
