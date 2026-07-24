from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverProcessingRun(TimestampMixin, Base):
    __tablename__ = "waiver_processing_runs"
    __table_args__ = (
        UniqueConstraint("league_id", "season", "week", "window_key", name="uq_waiver_processing_runs_window"),
        UniqueConstraint("idempotency_key", name="uq_waiver_processing_runs_idempotency_key"),
        CheckConstraint("waiver_type IN ('faab', 'priority')", name="ck_waiver_processing_runs_waiver_type"),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name="ck_waiver_processing_runs_status"),
        Index("ix_waiver_processing_runs_due", "scheduled_for", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    window_key: Mapped[str] = mapped_column(String(120), nullable=False)
    waiver_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    claims_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claims_won: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
