from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScoringAlertIncident(TimestampMixin, Base):
    """Durable, bounded deduplication state for operational scoring alerts."""

    __tablename__ = "scoring_alert_incidents"
    __table_args__ = (
        UniqueConstraint(
            "provider", "season", "week", "code", "resource_key",
            name="uq_scoring_alert_incidents_scope",
        ),
        Index("ix_scoring_alert_incidents_last_seen", "provider", "last_seen_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(500), nullable=False, default="week")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_emitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
