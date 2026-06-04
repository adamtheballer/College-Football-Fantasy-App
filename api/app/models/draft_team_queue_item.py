from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class DraftTeamQueueItem(TimestampMixin, Base):
    __tablename__ = "draft_team_queue_items"
    __table_args__ = (
        UniqueConstraint("draft_id", "team_id", "player_id", name="uq_draft_team_queue_items_unique_player"),
        UniqueConstraint("draft_id", "team_id", "priority", name="uq_draft_team_queue_items_unique_priority"),
        Index("ix_draft_team_queue_items_draft_team_priority", "draft_id", "team_id", "priority"),
        Index("ix_draft_team_queue_items_draft_player", "draft_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer, default=1)
