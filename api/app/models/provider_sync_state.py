from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProviderSyncState(TimestampMixin, Base):
    __tablename__ = "provider_sync_states"
    __table_args__ = (
        UniqueConstraint("provider", "feed", "scope_key", name="uq_provider_sync_states_provider_feed_scope"),
        Index("ix_provider_sync_states_provider_feed", "provider", "feed"),
        Index("ix_provider_sync_states_scope_key", "scope_key"),
        Index("ix_provider_sync_states_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    feed: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(500))
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
