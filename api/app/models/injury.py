from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Injury(TimestampMixin, Base):
    __tablename__ = "injuries"
    __table_args__ = (
        Index("ix_injuries_player_id", "player_id"),
        Index("ix_injuries_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="FULL")
    injury: Mapped[str | None] = mapped_column(String(200), nullable=True)
    return_timeline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    practice_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_game_time_decision: Mapped[bool] = mapped_column(Boolean, default=False)
    is_returning: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
