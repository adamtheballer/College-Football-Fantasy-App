from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueRivalryInvite(TimestampMixin, Base):
    __tablename__ = "league_rivalry_invites"
    __table_args__ = (
        Index("ix_league_rivalry_invites_league_status", "league_id", "status"),
        Index("ix_league_rivalry_invites_recipient_status", "recipient_team_id", "status"),
        Index("ix_league_rivalry_invites_expires_at", "expires_at"),
        Index("uq_league_rivalry_pending_sender", "league_id", "sender_team_id", unique=True, postgresql_where=text("status = 'PENDING'"), sqlite_where=text("status = 'PENDING'")),
        Index("uq_league_rivalry_pending_pair", "league_id", "sender_team_id", "recipient_team_id", unique=True, postgresql_where=text("status = 'PENDING'"), sqlite_where=text("status = 'PENDING'")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), index=True)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sender_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipient_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_rivalry_id: Mapped[int | None] = mapped_column(ForeignKey("league_rivalries.id", ondelete="SET NULL"), nullable=True)


class LeagueRivalry(TimestampMixin, Base):
    __tablename__ = "league_rivalries"
    __table_args__ = (UniqueConstraint("league_id", "team_a_id", "team_b_id", name="uq_league_rivalry_pair"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), index=True)
    team_a_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    team_b_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    team_a_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    team_b_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    manager_a_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    manager_b_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    # The invite points back to the rivalry with the database FK. Keeping this
    # audit ID scalar avoids a cyclic FK pair, which is not portable to the
    # SQLite test/runtime used by local alpha validation.
    accepted_invite_id: Mapped[int] = mapped_column(Integer, unique=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)


class LeagueRivalryBinding(Base):
    __tablename__ = "league_rivalry_bindings"
    __table_args__ = (UniqueConstraint("league_id", "team_id", name="uq_league_rivalry_binding_team"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rivalry_id: Mapped[int] = mapped_column(ForeignKey("league_rivalries.id", ondelete="CASCADE"), index=True)
