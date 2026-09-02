from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TradeReview(TimestampMixin, Base):
    __tablename__ = "trade_reviews"
    __table_args__ = (
        Index("ix_trade_reviews_trade_offer_id", "trade_offer_id"),
        Index("ix_trade_reviews_reviewer_user_id", "reviewer_user_id"),
        Index("ix_trade_reviews_action", "action"),
        Index(
            "uq_trade_reviews_vote_by_member",
            "trade_offer_id",
            "reviewer_user_id",
            unique=True,
            postgresql_where=text("action IN ('uphold', 'veto')"),
            sqlite_where=text("action IN ('uphold', 'veto')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_offer_id: Mapped[int] = mapped_column(ForeignKey("trade_offers.id", ondelete="CASCADE"))
    reviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    trade_offer = relationship("TradeOffer", back_populates="reviews")
