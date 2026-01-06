from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerStat(TimestampMixin, Base):
    __tablename__ = "player_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", name="uq_player_stats_player_season_week"),
        Index("ix_player_stats_player_id", "player_id"),
        Index("ix_player_stats_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50), default="sportsdata")
    stats: Mapped[dict] = mapped_column(JSON)
