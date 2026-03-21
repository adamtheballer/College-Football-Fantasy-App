from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class DraftPick(TimestampMixin, Base):
    __tablename__ = "draft_picks"
    __table_args__ = (
        UniqueConstraint("draft_id", "overall_pick", name="uq_draft_picks_draft_overall_pick"),
        UniqueConstraint("draft_id", "player_id", name="uq_draft_picks_draft_player"),
        Index("ix_draft_picks_draft_id", "draft_id"),
        Index("ix_draft_picks_team_id", "team_id"),
        Index("ix_draft_picks_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    made_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    round_number: Mapped[int] = mapped_column(Integer)
    round_pick: Mapped[int] = mapped_column(Integer)
    overall_pick: Mapped[int] = mapped_column(Integer)
