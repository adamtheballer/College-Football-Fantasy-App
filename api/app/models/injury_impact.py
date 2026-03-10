from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class InjuryImpact(TimestampMixin, Base):
    __tablename__ = "injury_impacts"
    __table_args__ = (
        Index("ix_injury_impacts_player_id", "player_id"),
        Index("ix_injury_impacts_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    delta_fpts: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
