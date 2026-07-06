from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScoringRun(TimestampMixin, Base):
    __tablename__ = "scoring_runs"
    __table_args__ = (
        Index("ix_scoring_runs_league_week", "league_id", "season", "week"),
        Index("ix_scoring_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=True)
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(50), default="sportsdata")
    status: Mapped[str] = mapped_column(String(50), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    players_updated: Mapped[int] = mapped_column(Integer, default=0)
    teams_updated: Mapped[int] = mapped_column(Integer, default=0)
    matchups_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    provider_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    rows_fetched: Mapped[int] = mapped_column(Integer, default=0)
    rows_matched: Mapped[int] = mapped_column(Integer, default=0)
    rows_unmatched: Mapped[int] = mapped_column(Integer, default=0)
    provider_events_seen: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    data_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_age_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_successful_run_id: Mapped[int | None] = mapped_column(ForeignKey("scoring_runs.id", ondelete="SET NULL"), nullable=True)
