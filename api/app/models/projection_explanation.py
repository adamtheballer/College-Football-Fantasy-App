from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProjectionExplanation(TimestampMixin, Base):
    __tablename__ = "projection_explanations"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", name="uq_projection_explanations_player_season_week"),
        Index("ix_projection_explanations_player_id", "player_id"),
        Index("ix_projection_explanations_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[list[dict]] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(50), default="v1")
