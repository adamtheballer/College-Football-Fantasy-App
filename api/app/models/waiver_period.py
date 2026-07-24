from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverPeriod(TimestampMixin, Base):
    """One league-scoped claim window and its immutable processing deadline."""

    __tablename__ = "waiver_periods"
    __table_args__ = (
        UniqueConstraint("league_id", "season", "week", "window_key", name="uq_waiver_periods_league_window"),
        CheckConstraint(
            "status IN ('scheduled', 'open', 'locked', 'processing', 'completed', 'failed')",
            name="ck_waiver_periods_status",
        ),
        Index("ix_waiver_periods_due", "processes_at", "status"),
        Index("ix_waiver_periods_league_status", "league_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    window_key: Mapped[str] = mapped_column(String(120), nullable=False)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
