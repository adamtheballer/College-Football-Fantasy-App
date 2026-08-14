from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScheduledNotification(TimestampMixin, Base):
    __tablename__ = "scheduled_notifications"
    __table_args__ = (
        Index("ix_scheduled_notifications_league_id", "league_id"),
        Index("ix_scheduled_notifications_user_id", "user_id"),
        Index("ix_scheduled_notifications_type", "notification_type"),
        Index("ix_scheduled_notifications_delivery_state", "scheduled_for", "sent_at", "canceled_at"),
        Index("ix_scheduled_notifications_claimable", "status", "scheduled_for", "claimed_at"),
        UniqueConstraint("event_key", name="uq_scheduled_notifications_event_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(50))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Durable event/outbox data. These remain nullable for legacy scheduled
    # draft rows; the processor backfills their template content safely.
    event_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    # ``notification_type`` is retained for compatibility with legacy draft
    # schedules. ``event_type`` is the canonical upper-case event contract.
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scope: Mapped[str] = mapped_column(String(30), default="direct_user", nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    category: Mapped[str] = mapped_column(String(30), default="SYSTEM", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
