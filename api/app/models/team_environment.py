from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TeamEnvironment(TimestampMixin, Base):
    __tablename__ = "team_environment"
    __table_args__ = (
        Index("ix_team_environment_team_name", "team_name"),
        Index("ix_team_environment_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_name: Mapped[str] = mapped_column(String(200))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    expected_plays: Mapped[float] = mapped_column(Float, default=0.0)
    expected_points: Mapped[float] = mapped_column(Float, default=0.0)
    pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    rush_rate: Mapped[float] = mapped_column(Float, default=0.0)
    red_zone_trips: Mapped[float] = mapped_column(Float, default=0.0)
    red_zone_td_rate: Mapped[float] = mapped_column(Float, default=0.0)
    pace_seconds_per_play: Mapped[float] = mapped_column(Float, default=0.0)
    implied_team_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
