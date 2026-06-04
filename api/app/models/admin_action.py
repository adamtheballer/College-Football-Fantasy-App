from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base


class AdminAction(Base):
    __tablename__ = "admin_actions"
    __table_args__ = (
        Index("ix_admin_actions_league_id_id", "league_id", "id"),
        Index("ix_admin_actions_league_action", "league_id", "action_type"),
        Index("ix_admin_actions_actor_user_id", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(120))
    target_type: Mapped[str] = mapped_column(String(120), default="league")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
