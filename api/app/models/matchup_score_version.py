from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base


class MatchupScoreVersion(Base):
    __tablename__ = "matchup_score_versions"
    __table_args__ = (
        UniqueConstraint("matchup_id", "version", name="uq_matchup_score_versions_matchup_version"),
        Index("ix_matchup_score_versions_matchup_id", "matchup_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    matchup_id: Mapped[int] = mapped_column(ForeignKey("matchups.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    home_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    away_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    scoring_run_id: Mapped[int | None] = mapped_column(ForeignKey("scoring_runs.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
