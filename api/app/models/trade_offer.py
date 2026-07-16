from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TradeOffer(TimestampMixin, Base):
    __tablename__ = "trade_offers"
    __table_args__ = (
        Index("ix_trade_offers_league_id", "league_id"),
        Index("ix_trade_offers_status", "status"),
        Index("ix_trade_offers_process_after", "process_after"),
        Index("ix_trade_offers_proposing_team_id", "proposing_team_id"),
        Index("ix_trade_offers_receiving_team_id", "receiving_team_id"),
        Index("ix_trade_offers_countered_from_trade_id", "countered_from_trade_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    proposing_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    receiving_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="proposed")
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    process_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    countered_from_trade_id: Mapped[int | None] = mapped_column(
        ForeignKey("trade_offers.id", ondelete="SET NULL"), nullable=True
    )

    items = relationship("TradeOfferItem", back_populates="trade_offer", cascade="all, delete-orphan")
    reviews = relationship("TradeReview", back_populates="trade_offer", cascade="all, delete-orphan")
    countered_from_trade = relationship("TradeOffer", remote_side="TradeOffer.id", uselist=False)
