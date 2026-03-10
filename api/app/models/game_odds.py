from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class GameOdds(TimestampMixin, Base):
    __tablename__ = "game_odds"
    __table_args__ = (
        Index("ix_game_odds_game_id", "game_id"),
        Index("ix_game_odds_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50), default="oddsapi")
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    over_under: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_implied: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_implied: Mapped[float | None] = mapped_column(Float, nullable=True)
