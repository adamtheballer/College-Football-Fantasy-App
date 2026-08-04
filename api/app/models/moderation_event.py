from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ModerationEvent(TimestampMixin, Base):
    """Privacy-preserving record of a blocked user-content submission."""

    __tablename__ = "moderation_events"
    __table_args__ = (
        Index("ix_moderation_events_actor_created", "actor_user_id", "created_at"),
        Index("ix_moderation_events_league_created", "league_id", "created_at"),
        Index("ix_moderation_events_reason_created", "reason_code", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    league_id: Mapped[int | None] = mapped_column(
        ForeignKey("leagues.id", ondelete="SET NULL"), nullable=True
    )
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
