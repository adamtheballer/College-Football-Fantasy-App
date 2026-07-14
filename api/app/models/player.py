from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Player(TimestampMixin, Base):
    __tablename__ = "players"
    __table_args__ = (
        Index("ix_players_external_id", "external_id"),
        Index("ix_players_sheet_adp", "sheet_adp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    position: Mapped[str] = mapped_column(String(10), index=True)
    school: Mapped[str] = mapped_column(String(200), index=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    player_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sheet_adp: Mapped[float | None] = mapped_column(Float, nullable=True)
    sheet_projected_season_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    sheet_projection_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sheet_source_sheet_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sheet_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    roster_entries = relationship("RosterEntry", back_populates="player", cascade="all, delete-orphan")

    @property
    def board_rank(self) -> int | None:
        if self.sheet_adp is None:
            return None
        return int(self.sheet_adp)
