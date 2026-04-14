from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class CFBStandingSnapshot(TimestampMixin, Base):
    __tablename__ = "cfb_standing_snapshots"
    __table_args__ = (
        UniqueConstraint("team_name", "conference", "season", name="uq_cfb_standing_snapshots_team_conf_season"),
        Index("ix_cfb_standing_snapshots_conf_season", "conference", "season"),
        Index("ix_cfb_standing_snapshots_season_rank", "season", "conference_rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_name: Mapped[str] = mapped_column(String(200), nullable=False)
    conference: Mapped[str] = mapped_column(String(10), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    conference_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conference_wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conference_losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="sportsdata")
