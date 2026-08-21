from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PushToken(TimestampMixin, Base):
    __tablename__ = "push_tokens"
    __table_args__ = (
        Index("ix_push_tokens_user_id", "user_id"),
        Index("ix_push_tokens_user_key", "user_key"),
        # A provider subscription can have retained, disabled historical rows.
        # Only one *active* owner may use it at a time.  Keep the SQLite
        # predicate too so local/CI metadata tests exercise the real rule.
        Index(
            "uq_push_tokens_active_device_token",
            "device_token",
            unique=True,
            postgresql_where=text("enabled = true"),
            sqlite_where=text("enabled = 1"),
        ),
        Index("ix_push_tokens_device_token", "device_token"),
        Index("ix_push_tokens_external_user_id", "external_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_token: Mapped[str] = mapped_column(String(255))
    # ``device_token`` is retained as the storage column for existing mobile
    # rows. New OneSignal registrations store a provider subscription ID here;
    # it is never returned by the authenticated API or logged.
    provider: Mapped[str] = mapped_column(String(30), default="legacy_expo", nullable=False)
    external_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform: Mapped[str] = mapped_column(String(30), default="unknown")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationPreference(TimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index("ix_notification_preferences_user_id", "user_id"),
        Index("ix_notification_preferences_user_key", "user_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    user_key: Mapped[str] = mapped_column(String(100))
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    draft_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    injury_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    injury_alert_scope: Mapped[str] = mapped_column(String(20), default="ALL")
    touchdown_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    waiver_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    projection_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    lineup_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    trade_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    chat_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    matchup_results: Mapped[bool] = mapped_column(Boolean, default=True)
    # Canonical product controls.  Legacy player-feed fields above remain
    # stored for backwards-compatible reads, but are not used for new events.
    matchup_start_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    matchup_result_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    big_play_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    long_rush_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    long_reception_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    long_pass_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        Index("ix_notification_logs_user_id", "user_id"),
        Index("ix_notification_logs_user_key", "user_key"),
        Index("ix_notification_logs_type", "alert_type"),
        Index("ix_notification_logs_user_read", "user_id", "read_at"),
        UniqueConstraint("event_key", name="uq_notification_logs_event_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String(30), default="SYSTEM", nullable=False)
    scope: Mapped[str] = mapped_column(String(30), default="direct_user", nullable=False)
    event_key: Mapped[str | None] = mapped_column(String(180), nullable=True)


class NotificationDeliveryAttempt(TimestampMixin, Base):
    __tablename__ = "notification_delivery_attempts"
    __table_args__ = (
        UniqueConstraint(
            "scheduled_notification_id",
            "channel",
            "attempt_number",
            name="uq_notification_delivery_attempt_schedule_channel_number",
        ),
        Index("ix_notification_delivery_attempts_scheduled_notification_id", "scheduled_notification_id"),
        Index("ix_notification_delivery_attempts_user_id", "user_id"),
        Index("ix_notification_delivery_attempts_status", "status"),
        Index("ix_notification_delivery_attempts_next_retry_at", "next_retry_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scheduled_notification_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_notifications.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(30))
    attempt_number: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationLeaguePreference(TimestampMixin, Base):
    __tablename__ = "notification_league_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "league_id", name="uq_notification_league_user_id"),
        Index("ix_notification_league_preferences_user_id", "user_id"),
        UniqueConstraint("user_key", "league_id", name="uq_notification_league_user"),
        Index("ix_notification_league_preferences_user_key", "user_key"),
        Index("ix_notification_league_preferences_league_id", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    user_key: Mapped[str] = mapped_column(String(100))
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    injury_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    big_play_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    projection_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    draft_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    trade_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    waiver_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    matchup_start_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    matchup_result_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    lineup_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    touchdown_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    long_rush_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    long_reception_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    long_pass_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
