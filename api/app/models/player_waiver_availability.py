from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerWaiverAvailability(TimestampMixin, Base):
    __tablename__ = "player_waiver_availability"
    __table_args__ = (
        UniqueConstraint("league_id", "player_id", name="uq_player_waiver_availability_league_player"),
        CheckConstraint(
            "state IN ('waivers', 'free_agent', 'waiver_locked', 'claim_pending', 'rostered', 'game_locked')",
            name="ck_player_waiver_availability_state",
        ),
        Index("ix_player_waiver_availability_due", "league_id", "state", "available_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="waivers")
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waiver_period_id: Mapped[int | None] = mapped_column(ForeignKey("waiver_periods.id", ondelete="SET NULL"), nullable=True)
    source_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    dropped_by_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
