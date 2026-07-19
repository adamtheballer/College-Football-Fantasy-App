from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerRoleSnapshot(TimestampMixin, Base):
    """Provider-backed role context used by the weekly projection build."""

    __tablename__ = "player_role_snapshots"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", name="uq_player_role_snapshot_week"),
        Index("ix_player_role_snapshot_player_id", "player_id"),
        Index("ix_player_role_snapshot_season_week", "season", "week"),
        Index("ix_player_role_snapshot_school_position", "school", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    school: Mapped[str] = mapped_column(String(200))
    position: Mapped[str] = mapped_column(String(10))
    depth_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role_status: Mapped[str] = mapped_column(String(30), default="unknown")
    snap_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_participation: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    carry_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    red_zone_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_line_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_usage_trend: Mapped[float | None] = mapped_column(Float, nullable=True)
