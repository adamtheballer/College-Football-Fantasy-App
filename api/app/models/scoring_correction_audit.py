from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScoringCorrectionAudit(TimestampMixin, Base):
    __tablename__ = "scoring_correction_audits"
    __table_args__ = (
        Index("ix_scoring_correction_audits_league_week", "league_id", "season", "week"),
        Index("ix_scoring_correction_audits_player", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    source_stat_id: Mapped[int | None] = mapped_column(ForeignKey("player_stats.id", ondelete="SET NULL"), nullable=True)
    affected_league_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    old_raw_json: Mapped[dict] = mapped_column(JSON, default={})
    new_raw_json: Mapped[dict] = mapped_column(JSON, default={})
    old_fantasy_points: Mapped[float] = mapped_column(Float, default=0.0)
    new_fantasy_points: Mapped[float] = mapped_column(Float, default=0.0)
    old_matchup_statuses: Mapped[dict] = mapped_column(JSON, default={})
    new_matchup_statuses: Mapped[dict] = mapped_column(JSON, default={})
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
