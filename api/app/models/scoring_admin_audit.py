from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScoringAdminAudit(TimestampMixin, Base):
    __tablename__ = "scoring_admin_audits"
    __table_args__ = (
        Index("ix_scoring_admin_audits_action", "action"),
        Index("ix_scoring_admin_audits_actor_user_id", "actor_user_id"),
        Index("ix_scoring_admin_audits_league_week", "league_id", "season", "week"),
        Index("ix_scoring_admin_audits_player_week", "player_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id", ondelete="SET NULL"), nullable=True)
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    affected_league_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
