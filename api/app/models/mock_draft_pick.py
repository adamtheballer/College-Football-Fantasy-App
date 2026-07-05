from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class MockDraftPick(TimestampMixin, Base):
    __tablename__ = "mock_draft_picks"
    __table_args__ = (
        UniqueConstraint("mock_draft_id", "pick_number", name="uq_mock_draft_picks_mock_pick_number"),
        UniqueConstraint("mock_draft_id", "player_id", name="uq_mock_draft_picks_mock_player"),
        Index("ix_mock_draft_picks_mock_draft_id", "mock_draft_id"),
        Index("ix_mock_draft_picks_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mock_draft_id: Mapped[int] = mapped_column(ForeignKey("mock_drafts.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    pick_number: Mapped[int] = mapped_column(Integer)
    round_number: Mapped[int] = mapped_column(Integer)
    round_pick: Mapped[int] = mapped_column(Integer)
    team_index: Mapped[int] = mapped_column(Integer)
    team_name: Mapped[str] = mapped_column(String(120))
    player_name: Mapped[str] = mapped_column(String(200))
    player_school: Mapped[str] = mapped_column(String(200))
    player_position: Mapped[str] = mapped_column(String(10))

    mock_draft = relationship("MockDraft", back_populates="picks")
