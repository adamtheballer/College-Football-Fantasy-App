from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class MockDraftRosterEntry(TimestampMixin, Base):
    __tablename__ = "mock_draft_roster_entries"
    __table_args__ = (
        UniqueConstraint("seat_id", "player_id", name="uq_mock_draft_roster_seat_player"),
        UniqueConstraint("session_id", "player_id", name="uq_mock_draft_roster_session_player"),
        Index("ix_mock_draft_roster_entries_session_id", "session_id"),
        Index("ix_mock_draft_roster_entries_seat_id", "seat_id"),
        Index("ix_mock_draft_roster_entries_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"))
    seat_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_seats.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    slot: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
