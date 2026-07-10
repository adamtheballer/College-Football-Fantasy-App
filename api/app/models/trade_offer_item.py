from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TradeOfferItem(TimestampMixin, Base):
    __tablename__ = "trade_offer_items"
    __table_args__ = (
        Index("ix_trade_offer_items_trade_offer_id", "trade_offer_id"),
        Index("ix_trade_offer_items_team_id", "team_id"),
        Index("ix_trade_offer_items_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_offer_id: Mapped[int] = mapped_column(ForeignKey("trade_offers.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    draft_pick_id: Mapped[int | None] = mapped_column(ForeignKey("draft_picks.id", ondelete="SET NULL"), nullable=True)
    item_type: Mapped[str] = mapped_column(String(30), default="player")

    trade_offer = relationship("TradeOffer", back_populates="items")
    player = relationship("Player")
