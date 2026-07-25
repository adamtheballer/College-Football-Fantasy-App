from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerAvailabilityEvent(TimestampMixin, Base):
    """A sourced, reviewable availability assertion with a bounded lifetime."""

    __tablename__ = "player_availability_events"
    __table_args__ = (
        Index("ix_player_availability_events_player_season_week", "player_id", "season", "week"),
        Index("ix_player_availability_events_effective_window", "season", "effective_from_week", "effective_until_week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    probability_active: Mapped[float] = mapped_column(Float, default=0.75)
    availability_multiplier: Mapped[float] = mapped_column(Float, default=0.75)
    snap_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(200))
    source_reliability: Mapped[float] = mapped_column(Float, default=0.5)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_from_week: Mapped[int] = mapped_column(Integer)
    effective_until_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
