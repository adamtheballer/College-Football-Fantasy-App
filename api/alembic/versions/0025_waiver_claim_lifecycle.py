"""waiver claim lifecycle

Revision ID: 0025_waiver_claim_lifecycle
Revises: 0024_provider_identity_v2
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_waiver_claim_lifecycle"
down_revision: str | None = "0024_provider_identity_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waiver_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("add_player_id", sa.Integer(), nullable=False),
        sa.Column("drop_player_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("priority_snapshot", sa.Integer(), nullable=True),
        sa.Column("faab_bid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["add_player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["drop_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_waiver_claims_add_player", "waiver_claims", ["league_id", "add_player_id"])
    op.create_index("ix_waiver_claims_league_status", "waiver_claims", ["league_id", "status"])
    op.create_index("ix_waiver_claims_team_status", "waiver_claims", ["team_id", "status"])

    op.create_table(
        "waiver_priorities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("faab_budget", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("faab_spent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "team_id", name="uq_waiver_priorities_league_team"),
    )
    op.create_index("ix_waiver_priorities_league_priority", "waiver_priorities", ["league_id", "priority"])

    op.create_table(
        "waiver_claim_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("waiver_claim_id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["waiver_claim_id"], ["waiver_claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_waiver_claim_audits_action", "waiver_claim_audits", ["action"])
    op.create_index("ix_waiver_claim_audits_claim_id", "waiver_claim_audits", ["waiver_claim_id"])


def downgrade() -> None:
    op.drop_index("ix_waiver_claim_audits_claim_id", table_name="waiver_claim_audits")
    op.drop_index("ix_waiver_claim_audits_action", table_name="waiver_claim_audits")
    op.drop_table("waiver_claim_audits")
    op.drop_index("ix_waiver_priorities_league_priority", table_name="waiver_priorities")
    op.drop_table("waiver_priorities")
    op.drop_index("ix_waiver_claims_team_status", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_league_status", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_add_player", table_name="waiver_claims")
    op.drop_table("waiver_claims")
