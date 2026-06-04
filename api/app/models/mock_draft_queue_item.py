from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class MockDraftQueueItem(TimestampMixin, Base):
    __tablename__ = "mock_draft_queue_items"
    __table_args__ = (
        UniqueConstraint("session_id", "seat_id", "player_id", name="uq_mock_draft_queue_items_unique_player"),
        UniqueConstraint("session_id", "seat_id", "priority", name="uq_mock_draft_queue_items_unique_priority"),
        Index("ix_mock_draft_queue_items_session_seat_priority", "session_id", "seat_id", "priority"),
        Index("ix_mock_draft_queue_items_session_player", "session_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"))
    seat_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_seats.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer, default=1)
