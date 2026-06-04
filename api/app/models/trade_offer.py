from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class TradeOffer(TimestampMixin, Base):
    __tablename__ = "trade_offers"
    __table_args__ = (
        UniqueConstraint("proposal_ref", name="uq_trade_offers_proposal_ref"),
        Index("ix_trade_offers_league_id", "league_id"),
        Index("ix_trade_offers_status", "status"),
        Index("ix_trade_offers_from_team_id", "from_team_id"),
        Index("ix_trade_offers_to_team_id", "to_team_id"),
        Index("ix_trade_offers_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_ref: Mapped[str] = mapped_column(String(32))
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    from_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    to_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), default="open")
    review_status: Mapped[str] = mapped_column(String(30), default="none")
    review_mode: Mapped[str] = mapped_column(String(30), default="commissioner")
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
