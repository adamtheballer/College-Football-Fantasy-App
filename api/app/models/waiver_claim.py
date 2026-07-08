from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverClaim(TimestampMixin, Base):
    __tablename__ = "waiver_claims"
    __table_args__ = (
        Index("ix_waiver_claims_league_id", "league_id"),
        Index("ix_waiver_claims_team_id", "team_id"),
        Index("ix_waiver_claims_status", "status"),
        Index("ix_waiver_claims_process_after", "process_after"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    add_player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    drop_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    bid_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_at_submission: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    process_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

