from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Player(TimestampMixin, Base):
    __tablename__ = "players"
    __table_args__ = (
        Index("ix_players_external_id", "external_id"),
        Index("ix_players_sheet_adp", "sheet_adp"),
        Index("ix_players_cfb27_rank", "cfb27_rank"),
        Index("ix_players_cfb27_overall", "cfb27_overall"),
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
    cfb27_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cfb27_overall: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cfb27_position_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cfb27_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    espn_height: Mapped[str | None] = mapped_column(String(40), nullable=True)
    espn_height_inches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    espn_weight: Mapped[str | None] = mapped_column(String(40), nullable=True)
    espn_birthplace: Mapped[str | None] = mapped_column(String(300), nullable=True)
    espn_birthplace_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    espn_birthplace_state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    espn_birthplace_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    espn_hometown: Mapped[str | None] = mapped_column(String(300), nullable=True)
    espn_date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    espn_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    espn_jersey: Mapped[str | None] = mapped_column(String(20), nullable=True)
    espn_headshot_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    espn_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    espn_profile_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    depth_chart_position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    depth_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bio_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    bio_source_sheet_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    bio_source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bio_imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def height(self) -> str | None:
        return self.espn_height

    @property
    def formatted_height(self) -> str | None:
        return self.espn_height

    @property
    def weight(self) -> str | None:
        return self.espn_weight

    @property
    def formatted_weight(self) -> str | None:
        return self.espn_weight

    @property
    def birthplace(self) -> str | None:
        return self.espn_birthplace

    roster_entries = relationship("RosterEntry", back_populates="player", cascade="all, delete-orphan")

    @property
    def board_rank(self) -> int | None:
        if self.cfb27_rank is not None:
            return self.cfb27_rank
        if self.sheet_adp is not None:
            return int(self.sheet_adp)
        return None
