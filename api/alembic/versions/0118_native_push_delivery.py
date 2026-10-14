"""Device-scoped native push and explicitly approved news; no events emitted by migration."""
from alembic import op
import sqlalchemy as sa

revision = "0118_native_push_delivery"
down_revision = "0117_app_review_request"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, kind in [("installation_id", sa.String(64)), ("installation_secret_hash", sa.String(64)), ("app_id", sa.String(64))]:
        op.add_column("push_tokens", sa.Column(name, kind, nullable=True))
    op.add_column("push_tokens", sa.Column("environment", sa.String(20), nullable=False, server_default="web"))
    op.create_index("ix_push_tokens_installation_id", "push_tokens", ["installation_id"])
    op.create_index("uq_push_tokens_active_installation", "push_tokens", ["installation_id"], unique=True,
                    postgresql_where=sa.text("enabled = true AND installation_id IS NOT NULL"))
    for name in ("push_drafts", "push_matchups", "push_injuries", "push_major_news"):
        op.add_column("notification_preferences", sa.Column(name, sa.Boolean(), nullable=False,
                       server_default=sa.text("false" if name == "push_major_news" else "true")))
    op.execute("UPDATE notification_delivery_attempts SET status = 'expired', error_message = 'native push rollout baseline', attempted_at = CURRENT_TIMESTAMP WHERE channel = 'push' AND status = 'pending' AND scheduled_notification_id IN (SELECT id FROM scheduled_notifications WHERE scheduled_for <= CURRENT_TIMESTAMP)")
    op.add_column("scheduled_notifications", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("scheduled_notifications", "league_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("notification_delivery_attempts", sa.Column("push_token_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_notification_attempt_push_token", "notification_delivery_attempts", "push_tokens", ["push_token_id"], ["id"], ondelete="RESTRICT")
    op.drop_constraint("uq_notification_delivery_attempt_schedule_channel_number", "notification_delivery_attempts", type_="unique")
    op.create_index("uq_notification_attempt_channel", "notification_delivery_attempts", ["scheduled_notification_id", "channel", "attempt_number"], unique=True, postgresql_where=sa.text("push_token_id IS NULL"))
    op.create_unique_constraint("uq_notification_attempt_device", "notification_delivery_attempts", ["scheduled_notification_id", "push_token_id", "attempt_number"])
    op.create_table("news_announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False), sa.Column("body", sa.String(400), nullable=False),
        sa.Column("audience", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Device fanout cannot be losslessly folded into the old one-channel ledger.
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM notification_delivery_attempts WHERE push_token_id IS NOT NULL) OR EXISTS (SELECT 1 FROM news_announcements)")):
        raise RuntimeError("Disable PUSH_NOTIFICATIONS_ENABLED and roll back application code; retain the push ledger.")
    op.drop_table("news_announcements")
    op.drop_constraint("uq_notification_attempt_device", "notification_delivery_attempts", type_="unique")
    op.drop_index("uq_notification_attempt_channel", table_name="notification_delivery_attempts")
    op.create_unique_constraint("uq_notification_delivery_attempt_schedule_channel_number", "notification_delivery_attempts", ["scheduled_notification_id", "channel", "attempt_number"])
    op.drop_constraint("fk_notification_attempt_push_token", "notification_delivery_attempts", type_="foreignkey")
    op.drop_column("notification_delivery_attempts", "push_token_id")
    op.alter_column("scheduled_notifications", "league_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("scheduled_notifications", "expires_at")
    for name in ("push_drafts", "push_matchups", "push_injuries", "push_major_news"):
        op.drop_column("notification_preferences", name)
    op.drop_index("uq_push_tokens_active_installation", table_name="push_tokens")
    op.drop_index("ix_push_tokens_installation_id", table_name="push_tokens")
    for name in ("installation_id", "installation_secret_hash", "app_id", "environment"):
        op.drop_column("push_tokens", name)
