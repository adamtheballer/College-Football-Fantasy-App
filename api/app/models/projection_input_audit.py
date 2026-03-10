from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProjectionInputAudit(TimestampMixin, Base):
    __tablename__ = "projection_inputs_audit"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", name="uq_projection_inputs_player_season_week"),
        Index("ix_projection_inputs_player_id", "player_id"),
        Index("ix_projection_inputs_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(50), default="v1")
    inputs: Mapped[dict] = mapped_column(JSON)
