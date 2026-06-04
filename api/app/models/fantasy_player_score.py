from sqlalchemy import Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class FantasyPlayerScore(TimestampMixin, Base):
    __tablename__ = "fantasy_player_scores"
    __table_args__ = (
        UniqueConstraint("league_id", "player_id", "season", "week", name="uq_fantasy_player_scores_player_week"),
        Index("ix_fantasy_player_scores_league_week", "league_id", "season", "week"),
        Index("ix_fantasy_player_scores_player_week", "player_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(50), default="computed")
