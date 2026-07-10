from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueMessage(TimestampMixin, Base):
    __tablename__ = "league_messages"
    __table_args__ = (
        Index("ix_league_messages_league_id", "league_id"),
        Index("ix_league_messages_message_type", "message_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message_type: Mapped[str] = mapped_column(String(50), default="system")
    body: Mapped[str] = mapped_column(Text)
