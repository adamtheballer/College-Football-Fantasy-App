"""Harden notification delivery into a durable idempotent outbox.

Revision ID: 0091_durable_notification_outbox
Revises: 0090_expand_league_icon_url
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0091_durable_notification_outbox"
down_revision = "0090_expand_league_icon_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("schedule_status", sa.String(length=40), nullable=True))
    op.add_column("push_tokens", sa.Column("provider", sa.String(length=30), nullable=False, server_default="legacy_expo"))
    op.add_column("push_tokens", sa.Column("external_user_id", sa.String(length=100), nullable=True))
    # Preserve every legacy subscription row.  Disabled rows are useful audit
    # history and must never be deleted merely to make a uniqueness constraint
    # possible.  Keep the newest enabled row for each subscription and make
    # the database the concurrency authority for *active* ownership only.
    op.execute(
        """
        WITH ranked_tokens AS (
          SELECT id, ROW_NUMBER() OVER (
            PARTITION BY device_token
            ORDER BY updated_at DESC NULLS LAST, id DESC
          ) AS row_number
          FROM push_tokens
          WHERE enabled = true
        )
        UPDATE push_tokens
        SET enabled = false
        WHERE id IN (SELECT id FROM ranked_tokens WHERE row_number > 1)
        """
    )
    op.create_index(
        "uq_push_tokens_active_device_token",
        "push_tokens",
        ["device_token"],
        unique=True,
        postgresql_where=sa.text("enabled = true"),
    )
    op.create_index("ix_push_tokens_external_user_id", "push_tokens", ["external_user_id"], unique=False)

    op.add_column("notification_preferences", sa.Column("trade_alerts", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("notification_preferences", sa.Column("chat_alerts", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("notification_preferences", sa.Column("matchup_results", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("notification_preferences", sa.Column("matchup_start_alerts", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("notification_preferences", sa.Column("matchup_result_alerts", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("notification_preferences", sa.Column("big_play_alerts", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notification_preferences", sa.Column("long_rush_alerts", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notification_preferences", sa.Column("long_reception_alerts", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notification_preferences", sa.Column("long_pass_alerts", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notification_preferences", sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"))

    op.add_column("notification_logs", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notification_logs", sa.Column("league_id", sa.Integer(), nullable=True))
    op.add_column("notification_logs", sa.Column("category", sa.String(length=30), nullable=False, server_default="SYSTEM"))
    op.add_column("notification_logs", sa.Column("scope", sa.String(length=30), nullable=False, server_default="direct_user"))
    op.add_column("notification_logs", sa.Column("event_key", sa.String(length=180), nullable=True))
    op.create_foreign_key("fk_notification_logs_league_id", "notification_logs", "leagues", ["league_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_notification_logs_user_read", "notification_logs", ["user_id", "read_at"], unique=False)
    op.create_unique_constraint("uq_notification_logs_event_key", "notification_logs", ["event_key"])

    op.add_column("scheduled_notifications", sa.Column("event_key", sa.String(length=180), nullable=True))
    op.execute("UPDATE scheduled_notifications SET event_key = CONCAT('legacy-scheduled:', id) WHERE event_key IS NULL")
    op.add_column("scheduled_notifications", sa.Column("title", sa.String(length=200), nullable=True))
    op.add_column("scheduled_notifications", sa.Column("event_type", sa.String(length=50), nullable=True))
    op.execute("UPDATE scheduled_notifications SET event_type = UPPER(notification_type) WHERE event_type IS NULL")
    op.add_column("scheduled_notifications", sa.Column("scope", sa.String(length=30), nullable=False, server_default="direct_user"))
    op.add_column("scheduled_notifications", sa.Column("body", sa.String(length=500), nullable=True))
    op.add_column("scheduled_notifications", sa.Column("payload", sa.JSON(), nullable=True))
    op.add_column("scheduled_notifications", sa.Column("category", sa.String(length=30), nullable=False, server_default="SYSTEM"))
    op.add_column("scheduled_notifications", sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"))
    op.add_column("scheduled_notifications", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scheduled_notifications", sa.Column("claim_heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scheduled_notifications", sa.Column("claimed_by", sa.String(length=100), nullable=True))
    op.add_column("scheduled_notifications", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    # Preserve the old terminal state during the cutover. Without this, every
    # already-sent legacy schedule would look pending to the new worker.
    op.execute(
        "UPDATE scheduled_notifications SET status = 'canceled', completed_at = canceled_at "
        "WHERE canceled_at IS NOT NULL"
    )
    op.execute(
        "UPDATE scheduled_notifications SET status = 'delivered', completed_at = sent_at "
        "WHERE canceled_at IS NULL AND sent_at IS NOT NULL"
    )
    op.create_unique_constraint("uq_scheduled_notifications_event_key", "scheduled_notifications", ["event_key"])
    op.create_index("ix_scheduled_notifications_claimable", "scheduled_notifications", ["status", "scheduled_for", "claimed_at"], unique=False)

    op.add_column("notification_delivery_attempts", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notification_delivery_attempts", sa.Column("provider_message_id", sa.String(length=255), nullable=True))
    op.add_column("notification_delivery_attempts", sa.Column("provider_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_notification_delivery_attempts_next_retry_at", "notification_delivery_attempts", ["next_retry_at"], unique=False)

    # League settings mirror the applicable global categories.  The legacy
    # player-feed columns stay in place for historical data compatibility.
    for name, default in (
        ("draft_alerts", sa.true()),
        ("trade_alerts", sa.true()),
        ("waiver_alerts", sa.true()),
        ("matchup_start_alerts", sa.true()),
        ("matchup_result_alerts", sa.true()),
        ("lineup_reminders", sa.true()),
        ("touchdown_alerts", sa.false()),
        ("long_rush_alerts", sa.false()),
        ("long_reception_alerts", sa.false()),
        ("long_pass_alerts", sa.false()),
    ):
        op.add_column("notification_league_preferences", sa.Column(name, sa.Boolean(), nullable=False, server_default=default))


def downgrade() -> None:
    op.drop_column("games", "schedule_status")
    for name in (
        "long_pass_alerts", "long_reception_alerts", "long_rush_alerts",
        "touchdown_alerts", "lineup_reminders", "matchup_result_alerts", "matchup_start_alerts",
        "waiver_alerts", "trade_alerts", "draft_alerts",
    ):
        op.drop_column("notification_league_preferences", name)
    op.drop_index("ix_notification_delivery_attempts_next_retry_at", table_name="notification_delivery_attempts")
    op.drop_column("notification_delivery_attempts", "provider_message_id")
    op.drop_column("notification_delivery_attempts", "provider_accepted_at")
    op.drop_column("notification_delivery_attempts", "next_retry_at")

    op.drop_index("ix_scheduled_notifications_claimable", table_name="scheduled_notifications")
    op.drop_constraint("uq_scheduled_notifications_event_key", "scheduled_notifications", type_="unique")
    op.drop_column("scheduled_notifications", "completed_at")
    op.drop_column("scheduled_notifications", "claimed_by")
    op.drop_column("scheduled_notifications", "claimed_at")
    op.drop_column("scheduled_notifications", "claim_heartbeat_at")
    op.drop_column("scheduled_notifications", "status")
    op.drop_column("scheduled_notifications", "category")
    op.drop_column("scheduled_notifications", "payload")
    op.drop_column("scheduled_notifications", "body")
    op.drop_column("scheduled_notifications", "title")
    op.drop_column("scheduled_notifications", "scope")
    op.drop_column("scheduled_notifications", "event_type")
    op.drop_column("scheduled_notifications", "event_key")

    op.drop_constraint("uq_notification_logs_event_key", "notification_logs", type_="unique")
    op.drop_index("ix_notification_logs_user_read", table_name="notification_logs")
    op.drop_constraint("fk_notification_logs_league_id", "notification_logs", type_="foreignkey")
    op.drop_column("notification_logs", "event_key")
    op.drop_column("notification_logs", "category")
    op.drop_column("notification_logs", "scope")
    op.drop_column("notification_logs", "league_id")
    op.drop_column("notification_logs", "read_at")

    op.drop_column("notification_preferences", "timezone")
    op.drop_column("notification_preferences", "matchup_results")
    op.drop_column("notification_preferences", "long_pass_alerts")
    op.drop_column("notification_preferences", "long_reception_alerts")
    op.drop_column("notification_preferences", "long_rush_alerts")
    op.drop_column("notification_preferences", "big_play_alerts")
    op.drop_column("notification_preferences", "matchup_result_alerts")
    op.drop_column("notification_preferences", "matchup_start_alerts")
    op.drop_column("notification_preferences", "chat_alerts")
    op.drop_column("notification_preferences", "trade_alerts")

    op.drop_index("ix_push_tokens_external_user_id", table_name="push_tokens")
    op.drop_index("uq_push_tokens_active_device_token", table_name="push_tokens")
    op.drop_column("push_tokens", "external_user_id")
    op.drop_column("push_tokens", "provider")
