"""league chat

Revision ID: 0040_league_chat
Revises: 0039_notification_delivery_state
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0040_league_chat"
down_revision = "0039_notification_delivery_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("parent_message_id", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_message_id"], ["league_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_league_messages_league_id_id", "league_messages", ["league_id", "id"])
    op.create_index("ix_league_messages_user_id", "league_messages", ["user_id"])
    op.create_index("ix_league_messages_parent_message_id", "league_messages", ["parent_message_id"])
    op.create_index("ix_league_messages_deleted_at", "league_messages", ["deleted_at"])

    op.create_table(
        "league_message_reads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("last_read_message_id", sa.Integer(), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["last_read_message_id"], ["league_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "league_id", name="uq_league_message_reads_user_league"),
    )
    op.create_index("ix_league_message_reads_league_id", "league_message_reads", ["league_id"])
    op.create_index("ix_league_message_reads_user_id", "league_message_reads", ["user_id"])

    op.create_table(
        "league_message_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["league_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "reporter_user_id", name="uq_league_message_reports_message_reporter"),
    )
    op.create_index("ix_league_message_reports_message_id", "league_message_reports", ["message_id"])
    op.create_index("ix_league_message_reports_reporter_user_id", "league_message_reports", ["reporter_user_id"])
    op.create_index("ix_league_message_reports_status", "league_message_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_league_message_reports_status", table_name="league_message_reports")
    op.drop_index("ix_league_message_reports_reporter_user_id", table_name="league_message_reports")
    op.drop_index("ix_league_message_reports_message_id", table_name="league_message_reports")
    op.drop_table("league_message_reports")

    op.drop_index("ix_league_message_reads_user_id", table_name="league_message_reads")
    op.drop_index("ix_league_message_reads_league_id", table_name="league_message_reads")
    op.drop_table("league_message_reads")

    op.drop_index("ix_league_messages_deleted_at", table_name="league_messages")
    op.drop_index("ix_league_messages_parent_message_id", table_name="league_messages")
    op.drop_index("ix_league_messages_user_id", table_name="league_messages")
    op.drop_index("ix_league_messages_league_id_id", table_name="league_messages")
    op.drop_table("league_messages")
