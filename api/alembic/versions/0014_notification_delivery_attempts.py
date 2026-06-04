"""notification delivery attempts

Revision ID: 0014_notif_attempts
Revises: 0013_league_invariants
Create Date: 2026-03-21 21:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_notif_attempts"
down_revision = "0013_league_invariants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_delivery_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "scheduled_notification_id",
            sa.Integer(),
            sa.ForeignKey("scheduled_notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "scheduled_notification_id",
            "channel",
            "attempt_number",
            name="uq_notification_delivery_attempt_schedule_channel_number",
        ),
    )
    op.create_index(
        "ix_notification_delivery_attempts_scheduled_notification_id",
        "notification_delivery_attempts",
        ["scheduled_notification_id"],
    )
    op.create_index(
        "ix_notification_delivery_attempts_user_id",
        "notification_delivery_attempts",
        ["user_id"],
    )
    op.create_index(
        "ix_notification_delivery_attempts_status",
        "notification_delivery_attempts",
        ["status"],
    )
    op.create_index(
        "ix_scheduled_notifications_delivery_state",
        "scheduled_notifications",
        ["scheduled_for", "sent_at", "canceled_at"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO notification_delivery_attempts (
                scheduled_notification_id,
                user_id,
                channel,
                attempt_number,
                status
            )
            SELECT sn.id, sn.user_id, channel_values.channel, 1, 'pending'
            FROM scheduled_notifications AS sn
            JOIN (
                SELECT 'push' AS channel
                UNION ALL
                SELECT 'email' AS channel
            ) AS channel_values ON 1 = 1
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_notifications_delivery_state", table_name="scheduled_notifications")
    op.drop_index("ix_notification_delivery_attempts_status", table_name="notification_delivery_attempts")
    op.drop_index("ix_notification_delivery_attempts_user_id", table_name="notification_delivery_attempts")
    op.drop_index(
        "ix_notification_delivery_attempts_scheduled_notification_id",
        table_name="notification_delivery_attempts",
    )
    op.drop_table("notification_delivery_attempts")
