from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerSeasonContext(TimestampMixin, Base):
    __tablename__ = "player_season_contexts"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season_contexts_player_season"),
        Index("ix_player_season_contexts_team_season", "current_team_id", "season"),
        Index("ix_player_season_contexts_season_active", "season", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    current_team_id: Mapped[int] = mapped_column(ForeignKey("college_teams.id", ondelete="RESTRICT"))
    historical_team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    depth_position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False)
    current_team_verification_status: Mapped[str] = mapped_column(String(40), default="legacy_player_record")
    identity_source: Mapped[str] = mapped_column(String(100), default="player.school")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    availability_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    availability_multiplier: Mapped[float] = mapped_column(Float, default=0.75)
    role_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    role_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_review_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manual_review_status: Mapped[str] = mapped_column(String(40), default="unreviewed")
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
