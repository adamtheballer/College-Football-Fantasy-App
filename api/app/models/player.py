from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Player(TimestampMixin, Base):
    __tablename__ = "players"
    __table_args__ = (
        Index("ix_players_external_id", "external_id"),
        Index("ix_players_position", "position"),
        Index("ix_players_school", "school"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    position: Mapped[str] = mapped_column(String(10), index=True)
    school: Mapped[str] = mapped_column(String(200), index=True)

    roster_entries = relationship("RosterEntry", back_populates="player", cascade="all, delete-orphan")
