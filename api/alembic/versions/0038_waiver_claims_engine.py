"""waiver claims engine

Revision ID: 0038_waiver_claims_engine
Revises: 0037_trade_offers_workflow
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0038_waiver_claims_engine"
down_revision = "0037_trade_offers_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("league_settings") as batch_op:
        batch_op.add_column(sa.Column("waiver_mode", sa.String(length=50), nullable=False, server_default="faab"))
        batch_op.add_column(sa.Column("waiver_period_hours", sa.Integer(), nullable=False, server_default="24"))
        batch_op.add_column(sa.Column("weekly_waiver_day", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("faab_budget", sa.Integer(), nullable=False, server_default="100"))
        batch_op.add_column(sa.Column("allow_zero_dollar_bids", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.create_table(
        "waiver_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("add_player_id", sa.Integer(), nullable=False),
        sa.Column("drop_player_id", sa.Integer(), nullable=True),
        sa.Column("bid_amount", sa.Integer(), nullable=True),
        sa.Column("priority_at_submission", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("process_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["add_player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["drop_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_waiver_claims_league_id", "waiver_claims", ["league_id"])
    op.create_index("ix_waiver_claims_team_id", "waiver_claims", ["team_id"])
    op.create_index("ix_waiver_claims_status", "waiver_claims", ["status"])
    op.create_index("ix_waiver_claims_process_after", "waiver_claims", ["process_after"])

    op.create_table(
        "waiver_priority",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("faab_remaining", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "team_id", name="uq_waiver_priority_league_team"),
    )
    op.create_index("ix_waiver_priority_league_id", "waiver_priority", ["league_id"])
    op.create_index("ix_waiver_priority_team_id", "waiver_priority", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_waiver_priority_team_id", table_name="waiver_priority")
    op.drop_index("ix_waiver_priority_league_id", table_name="waiver_priority")
    op.drop_table("waiver_priority")

    op.drop_index("ix_waiver_claims_process_after", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_status", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_team_id", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_league_id", table_name="waiver_claims")
    op.drop_table("waiver_claims")

    with op.batch_alter_table("league_settings") as batch_op:
        batch_op.drop_column("allow_zero_dollar_bids")
        batch_op.drop_column("faab_budget")
        batch_op.drop_column("weekly_waiver_day")
        batch_op.drop_column("waiver_period_hours")
        batch_op.drop_column("waiver_mode")
