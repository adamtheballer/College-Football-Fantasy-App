from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScoringJobLock(TimestampMixin, Base):
    __tablename__ = "scoring_job_locks"
    __table_args__ = (
        UniqueConstraint("lock_key", name="uq_scoring_job_locks_lock_key"),
        Index("ix_scoring_job_locks_key", "lock_key"),
        Index("ix_scoring_job_locks_status", "status"),
        Index("ix_scoring_job_locks_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lock_key: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    league_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    worker_id: Mapped[str] = mapped_column(String(120), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
