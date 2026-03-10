from sqlalchemy import Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WeeklyProjection(TimestampMixin, Base):
    __tablename__ = "weekly_projections"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", name="uq_weekly_projections_player_season_week"),
        Index("ix_weekly_projections_player_id", "player_id"),
        Index("ix_weekly_projections_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)

    pass_attempts: Mapped[float] = mapped_column(Float, default=0.0)
    rush_attempts: Mapped[float] = mapped_column(Float, default=0.0)
    targets: Mapped[float] = mapped_column(Float, default=0.0)
    receptions: Mapped[float] = mapped_column(Float, default=0.0)
    expected_plays: Mapped[float] = mapped_column(Float, default=0.0)
    expected_rush_per_play: Mapped[float] = mapped_column(Float, default=0.0)
    expected_td_per_play: Mapped[float] = mapped_column(Float, default=0.0)

    pass_yards: Mapped[float] = mapped_column(Float, default=0.0)
    rush_yards: Mapped[float] = mapped_column(Float, default=0.0)
    rec_yards: Mapped[float] = mapped_column(Float, default=0.0)

    pass_tds: Mapped[float] = mapped_column(Float, default=0.0)
    rush_tds: Mapped[float] = mapped_column(Float, default=0.0)
    rec_tds: Mapped[float] = mapped_column(Float, default=0.0)
    interceptions: Mapped[float] = mapped_column(Float, default=0.0)

    fantasy_points: Mapped[float] = mapped_column(Float, default=0.0)
    floor: Mapped[float] = mapped_column(Float, default=0.0)
    ceiling: Mapped[float] = mapped_column(Float, default=0.0)
    boom_prob: Mapped[float] = mapped_column(Float, default=0.0)
    bust_prob: Mapped[float] = mapped_column(Float, default=0.0)
    qb_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
