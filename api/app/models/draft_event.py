from sqlalchemy import ForeignKey, Index, JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class DraftEvent(TimestampMixin, Base):
    __tablename__ = "draft_events"
    __table_args__ = (
        Index("ix_draft_events_draft_id", "draft_id"),
        Index("ix_draft_events_league_id", "league_id"),
        Index("ix_draft_events_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

