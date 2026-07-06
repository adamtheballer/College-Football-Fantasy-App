from sqlalchemy import Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class CFBRankingSnapshot(TimestampMixin, Base):
    __tablename__ = "cfb_ranking_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "poll",
            "season",
            "week",
            "team_external_id",
            name="uq_cfb_rankings_provider_poll_week_team",
        ),
        Index("ix_cfb_rankings_season_week", "season", "week"),
        Index("ix_cfb_rankings_poll_rank", "poll", "rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), default="espn", nullable=False)
    poll: Mapped[str] = mapped_column(String(120), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    team_external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    team_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_place_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    record_summary: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
