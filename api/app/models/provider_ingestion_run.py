from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProviderIngestionRun(TimestampMixin, Base):
    __tablename__ = "provider_ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), default="espn", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    targets: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cache_hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_misses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requests_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_stale_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_write_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
