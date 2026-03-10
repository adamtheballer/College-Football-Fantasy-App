from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class DefenseVsPosition(TimestampMixin, Base):
    __tablename__ = "defense_vs_position"
    __table_args__ = (
        Index("ix_defense_vs_position_team_name", "team_name"),
        Index("ix_defense_vs_position_season_week", "season", "week"),
        Index("ix_defense_vs_position_position", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_name: Mapped[str] = mapped_column(String(200))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(10))

    grade: Mapped[str] = mapped_column(String(4), default="C")
    rank: Mapped[int] = mapped_column(Integer, default=65)

    yards_per_target: Mapped[float] = mapped_column(Float, default=7.5)
    yards_per_rush: Mapped[float] = mapped_column(Float, default=4.2)
    pass_td_rate: Mapped[float] = mapped_column(Float, default=0.04)
    rush_td_rate: Mapped[float] = mapped_column(Float, default=0.03)
    explosive_rate: Mapped[float] = mapped_column(Float, default=0.1)
    pressure_rate: Mapped[float] = mapped_column(Float, default=0.22)
