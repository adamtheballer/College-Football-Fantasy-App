from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverClaim(TimestampMixin, Base):
    __tablename__ = "waiver_claims"
    __table_args__ = (
        Index("ix_waiver_claims_league_status", "league_id", "status"),
        Index("ix_waiver_claims_team_status", "team_id", "status"),
        Index("ix_waiver_claims_add_player", "league_id", "add_player_id"),
        Index("ix_waiver_claims_process_after", "process_after"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    add_player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    drop_roster_entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drop_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    priority_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    faab_bid: Mapped[int] = mapped_column(Integer, default=0)
    process_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
