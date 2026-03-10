from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class DefenseRating(TimestampMixin, Base):
    __tablename__ = "defense_ratings"
    __table_args__ = (
        Index("ix_defense_ratings_team_name", "team_name"),
        Index("ix_defense_ratings_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_name: Mapped[str] = mapped_column(String(200))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)

    pass_def_score: Mapped[float] = mapped_column(Float, default=0.0)
    rush_def_score: Mapped[float] = mapped_column(Float, default=0.0)
    pass_def_tier: Mapped[str] = mapped_column(String(10), default="Average")
    rush_def_tier: Mapped[str] = mapped_column(String(10), default="Average")

    pass_yards_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    pass_catch_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    pass_td_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    pass_turnover_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    rush_yards_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    rush_success_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    rush_td_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
