from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class WaiverClaim(TimestampMixin, Base):
    __tablename__ = "waiver_claims"
    __table_args__ = (
        Index("ix_waiver_claims_league_id_status", "league_id", "status"),
        Index("ix_waiver_claims_league_id_created_at", "league_id", "created_at"),
        Index("ix_waiver_claims_team_id_status", "team_id", "status"),
        Index("ix_waiver_claims_add_player_id", "add_player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    add_player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    drop_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)

    bid_amount: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    process_batch_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    processed_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
