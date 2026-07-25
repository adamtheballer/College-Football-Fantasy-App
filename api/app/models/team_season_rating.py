from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TeamSeasonRating(TimestampMixin, Base):
    __tablename__ = "team_season_ratings"
    __table_args__ = (
        UniqueConstraint("team_id", "season", name="uq_team_season_ratings_team_season"),
        Index("ix_team_season_ratings_season", "season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("college_teams.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    offensive_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    offensive_rank: Mapped[int] = mapped_column(Integer)
    offensive_percentile: Mapped[float] = mapped_column(Float)
    offense_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    defensive_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    defensive_rank: Mapped[int] = mapped_column(Integer)
    defensive_percentile: Mapped[float] = mapped_column(Float)
    opponent_defense_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(100), default="manual_import")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )
