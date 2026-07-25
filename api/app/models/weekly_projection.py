from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, and_
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


BETA_PROJECTION_MODEL_VERSION = "v3_beta_weighted"


class WeeklyProjection(TimestampMixin, Base):
    __tablename__ = "weekly_projections"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", "projection_version", name="uq_weekly_projections_player_season_week_version"),
        Index("ix_weekly_projections_player_id", "player_id"),
        Index("ix_weekly_projections_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    projection_version: Mapped[str] = mapped_column(String(20), default="FINAL")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    field_goals_made_0_to_49: Mapped[float] = mapped_column(Float, default=0.0)
    field_goals_made_50_plus: Mapped[float] = mapped_column(Float, default=0.0)
    extra_points_made: Mapped[float] = mapped_column(Float, default=0.0)

    neutral_baseline: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_games_played: Mapped[int] = mapped_column(Integer, default=0)
    baseline_source: Mapped[str] = mapped_column(String(40), default="position_default")
    team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id", ondelete="SET NULL"), nullable=True)
    opponent_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id", ondelete="SET NULL"), nullable=True)
    projection_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    availability_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    usage_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    offense_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    opponent_defense_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    fallback_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), default=BETA_PROJECTION_MODEL_VERSION)
    fantasy_points: Mapped[float] = mapped_column(Float, default=0.0)
    floor: Mapped[float] = mapped_column(Float, default=0.0)
    ceiling: Mapped[float] = mapped_column(Float, default=0.0)
    boom_prob: Mapped[float] = mapped_column(Float, default=0.0)
    bust_prob: Mapped[float] = mapped_column(Float, default=0.0)
    qb_rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    @classmethod
    def beta_ready_clause(cls):
        return and_(
            cls.model_version == BETA_PROJECTION_MODEL_VERSION,
            cls.team_id.is_not(None),
            cls.projection_status.in_(("ACTIVE", "BYE", "OUT")),
        )
