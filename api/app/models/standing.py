from sqlalchemy import Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Standing(TimestampMixin, Base):
    __tablename__ = "standings"
    __table_args__ = (
        UniqueConstraint("league_id", "team_id", "season", "week", name="uq_standings_team_season_week"),
        Index("ix_standings_league_week", "league_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    ties: Mapped[int] = mapped_column(Integer, default=0)
    points_for: Mapped[float] = mapped_column(Float, default=0.0)
    points_against: Mapped[float] = mapped_column(Float, default=0.0)
