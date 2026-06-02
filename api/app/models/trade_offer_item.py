from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TradeOfferItem(TimestampMixin, Base):
    __tablename__ = "trade_offer_items"
    __table_args__ = (
        Index("ix_trade_offer_items_trade_offer_id", "trade_offer_id"),
        Index("ix_trade_offer_items_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_offer_id: Mapped[int] = mapped_column(ForeignKey("trade_offers.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    side: Mapped[str] = mapped_column(String(20))
