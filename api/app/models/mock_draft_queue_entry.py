from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class MockDraftQueueEntry(TimestampMixin, Base):
    __tablename__ = "mock_draft_queue_entries"
    __table_args__ = (
        UniqueConstraint("mock_draft_id", "player_id", name="uq_mock_draft_queue_player"),
        UniqueConstraint("mock_draft_id", "priority", name="uq_mock_draft_queue_priority"),
        Index("ix_mock_draft_queue_mock_draft_id", "mock_draft_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mock_draft_id: Mapped[int] = mapped_column(ForeignKey("mock_drafts.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer)
