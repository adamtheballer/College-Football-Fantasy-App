from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerSeasonRank(TimestampMixin, Base):
    __tablename__ = "player_season_ranks"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "through_week", name="uq_player_season_rank_snapshot"),
        Index("ix_player_season_ranks_player_season", "player_id", "season"),
        Index("ix_player_season_ranks_season_week_position_rank", "season", "through_week", "position", "position_rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    through_week: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(10))
    fantasy_points: Mapped[float] = mapped_column(Float)
    position_rank: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
