"""notification delivery state

Revision ID: 0039_notification_delivery_state
Revises: 0038_waiver_claims_engine
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0039_notification_delivery_state"
down_revision = "0038_waiver_claims_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notification_preferences") as batch_op:
        batch_op.add_column(sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("category_toggles", sa.JSON(), nullable=True))

    with op.batch_alter_table("notification_logs") as batch_op:
        batch_op.add_column(sa.Column("league_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("delivery_state", sa.String(length=30), nullable=False, server_default="sent"))
        batch_op.add_column(sa.Column("dedupe_key", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_entity_type", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("source_entity_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("deep_link", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key("fk_notification_logs_league_id", "leagues", ["league_id"], ["id"], ondelete="SET NULL")

    op.create_index("ix_notification_logs_league_id", "notification_logs", ["league_id"])
    op.create_index("ix_notification_logs_delivery_state", "notification_logs", ["delivery_state"])
    op.create_index("ix_notification_logs_dedupe_user_id", "notification_logs", ["user_id", "dedupe_key"], unique=True)
    op.create_index("ix_notification_logs_dedupe_user_key", "notification_logs", ["user_key", "dedupe_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_notification_logs_dedupe_user_key", table_name="notification_logs")
    op.drop_index("ix_notification_logs_dedupe_user_id", table_name="notification_logs")
    op.drop_index("ix_notification_logs_delivery_state", table_name="notification_logs")
    op.drop_index("ix_notification_logs_league_id", table_name="notification_logs")

    with op.batch_alter_table("notification_logs") as batch_op:
        batch_op.drop_constraint("fk_notification_logs_league_id", type_="foreignkey")
        batch_op.drop_column("dismissed_at")
        batch_op.drop_column("read_at")
        batch_op.drop_column("deep_link")
        batch_op.drop_column("source_entity_id")
        batch_op.drop_column("source_entity_type")
        batch_op.drop_column("dedupe_key")
        batch_op.drop_column("delivery_state")
        batch_op.drop_column("league_id")

    with op.batch_alter_table("notification_preferences") as batch_op:
        batch_op.drop_column("category_toggles")
        batch_op.drop_column("in_app_enabled")
