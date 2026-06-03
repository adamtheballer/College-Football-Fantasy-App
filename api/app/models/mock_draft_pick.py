from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class MockDraftPick(TimestampMixin, Base):
    __tablename__ = "mock_draft_picks"
    __table_args__ = (
        UniqueConstraint("session_id", "overall_pick", name="uq_mock_draft_picks_session_overall_pick"),
        UniqueConstraint("session_id", "player_id", name="uq_mock_draft_picks_session_player"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_mock_draft_picks_session_idempotency_key"),
        Index("ix_mock_draft_picks_session_id", "session_id"),
        Index("ix_mock_draft_picks_seat_id", "seat_id"),
        Index("ix_mock_draft_picks_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"))
    seat_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_seats.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    made_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    round_number: Mapped[int] = mapped_column(Integer)
    round_pick: Mapped[int] = mapped_column(Integer)
    overall_pick: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
