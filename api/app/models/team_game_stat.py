from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TeamGameStat(TimestampMixin, Base):
    __tablename__ = "team_game_stats"
    __table_args__ = (
        UniqueConstraint("team_name", "game_id", name="uq_team_game_stats_team_game"),
        Index("ix_team_game_stats_team_name", "team_name"),
        Index("ix_team_game_stats_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_name: Mapped[str] = mapped_column(String(200))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50), default="cfbd")
    stats: Mapped[dict] = mapped_column(JSON)
