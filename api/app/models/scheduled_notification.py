from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScheduledNotification(TimestampMixin, Base):
    __tablename__ = "scheduled_notifications"
    __table_args__ = (
        Index("ix_scheduled_notifications_league_id", "league_id"),
        Index("ix_scheduled_notifications_user_id", "user_id"),
        Index("ix_scheduled_notifications_type", "notification_type"),
        Index("ix_scheduled_notifications_delivery_state", "scheduled_for", "sent_at", "canceled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(50))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
