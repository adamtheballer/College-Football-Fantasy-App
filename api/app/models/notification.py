from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PushToken(TimestampMixin, Base):
    __tablename__ = "push_tokens"
    __table_args__ = (
        Index("ix_push_tokens_user_id", "user_id"),
        Index("ix_push_tokens_user_key", "user_key"),
        Index("ix_push_tokens_device_token", "device_token"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_token: Mapped[str] = mapped_column(String(255))
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
    touchdown_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    waiver_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    projection_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    lineup_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(10), nullable=True)


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        Index("ix_notification_logs_user_id", "user_id"),
        Index("ix_notification_logs_user_key", "user_key"),
        Index("ix_notification_logs_type", "alert_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


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
