from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class DraftQueueEntry(TimestampMixin, Base):
    __tablename__ = "draft_queue_entries"
    __table_args__ = (
        UniqueConstraint("draft_id", "team_id", "player_id", name="uq_draft_queue_team_player"),
        UniqueConstraint("draft_id", "team_id", "priority", name="uq_draft_queue_team_priority"),
        Index("ix_draft_queue_entries_draft_team", "draft_id", "team_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer)
