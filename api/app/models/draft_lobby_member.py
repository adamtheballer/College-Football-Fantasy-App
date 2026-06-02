from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class DraftLobbyMember(TimestampMixin, Base):
    __tablename__ = "draft_lobby_members"
    __table_args__ = (
        UniqueConstraint("draft_id", "team_id", name="uq_draft_lobby_members_draft_team"),
        UniqueConstraint("draft_id", "user_id", name="uq_draft_lobby_members_draft_user"),
        Index("ix_draft_lobby_members_draft_id", "draft_id"),
        Index("ix_draft_lobby_members_team_id", "team_id"),
        Index("ix_draft_lobby_members_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
