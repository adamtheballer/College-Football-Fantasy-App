from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class NewsItem(TimestampMixin, Base):
    __tablename__ = "news_items"
    __table_args__ = (
        Index("ix_news_items_category", "category"),
        Index("ix_news_items_status", "status"),
        Index("ix_news_items_published_at", "published_at"),
        Index("ix_news_items_fantasy_relevance_score", "fantasy_relevance_score"),
        Index("ix_news_items_player_id", "player_id"),
        Index("ix_news_items_canonical_team", "canonical_team"),
        Index("ix_news_items_source_name", "source_name"),
        Index("ix_news_items_content_hash", "content_hash", unique=True),
        Index("ix_news_items_source_url", "source_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_name: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(String(900))
    source_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="general")
    status: Mapped[str] = mapped_column(String(30), default="new")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    player_name_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_name_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    canonical_team: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[str | None] = mapped_column(String(10), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    fantasy_relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    fantasy_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
