"""Add immutable Saturday Pick 6 review audit records.

Revision ID: 0109_saturday_pick_content_audit
Revises: 0108_league_trade_vote
"""

import sqlalchemy as sa
from alembic import op


revision = "0109_saturday_pick_content_audit"
down_revision = "0108_league_trade_vote"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saturday_pick_content_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contest_id", sa.Integer(), sa.ForeignKey("saturday_pick_contests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_saturday_pick_content_audits_contest_created",
        "saturday_pick_content_audits",
        ["contest_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_saturday_pick_content_audits_contest_created", table_name="saturday_pick_content_audits")
    op.drop_table("saturday_pick_content_audits")
