from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScheduleSyncIssue(TimestampMixin, Base):
    """Durable, operator-visible exceptions from a safe schedule sync.

    A source ambiguity is evidence to review, never permission to guess a
    kickoff.  Open issues are updated in place on retries so a recurring TBD
    does not create unbounded duplicate rows.
    """

    __tablename__ = "schedule_sync_issues"
    __table_args__ = (
        Index("ix_schedule_sync_issues_scope", "season", "week", "issue_type"),
        Index("ix_schedule_sync_issues_open", "resolved_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    team_name: Mapped[str] = mapped_column(String(200), nullable=False)
    opponent_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(64), nullable=False)
    current_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
