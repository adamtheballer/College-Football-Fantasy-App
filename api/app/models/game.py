from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Game(TimestampMixin, Base):
    __tablename__ = "games"
    __table_args__ = (
        Index("ix_games_season_week", "season", "week"),
        Index("ix_games_external_id", "external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    season_type: Mapped[str] = mapped_column(String(20), default="regular")
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    home_team: Mapped[str] = mapped_column(String(200))
    away_team: Mapped[str] = mapped_column(String(200))
    home_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    neutral_site: Mapped[bool] = mapped_column(Boolean, default=False)
