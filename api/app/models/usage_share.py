from sqlalchemy import Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class UsageShare(TimestampMixin, Base):
    __tablename__ = "usage_shares"
    __table_args__ = (
        Index("ix_usage_shares_player_id", "player_id"),
        Index("ix_usage_shares_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)

    rush_share: Mapped[float] = mapped_column(Float, default=0.0)
    target_share: Mapped[float] = mapped_column(Float, default=0.0)
    red_zone_share: Mapped[float] = mapped_column(Float, default=0.0)
    inside_five_share: Mapped[float] = mapped_column(Float, default=0.0)
    snap_share: Mapped[float] = mapped_column(Float, default=0.0)
    route_share: Mapped[float] = mapped_column(Float, default=0.0)
