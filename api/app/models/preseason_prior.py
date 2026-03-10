from sqlalchemy import ForeignKey, Index, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PreseasonPrior(TimestampMixin, Base):
    __tablename__ = "preseason_priors"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_preseason_priors_player_season"),
        Index("ix_preseason_priors_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    priors: Mapped[dict] = mapped_column(JSON)
