from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TradeReview(TimestampMixin, Base):
    __tablename__ = "trade_reviews"
    __table_args__ = (
        Index("ix_trade_reviews_trade_offer_id", "trade_offer_id"),
        Index("ix_trade_reviews_reviewer_user_id", "reviewer_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_offer_id: Mapped[int] = mapped_column(ForeignKey("trade_offers.id", ondelete="CASCADE"))
    reviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    trade_offer = relationship("TradeOffer", back_populates="reviews")
