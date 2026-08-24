from sqlalchemy import ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("league_id", "name", name="uq_team_league_name"),
        UniqueConstraint("league_id", "owner_user_id", name="uq_team_league_owner"),
        Index("ix_teams_league_id", "league_id"),
        Index("ix_teams_league_draft_position", "league_id", "draft_position", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Null is intentional before a commissioner finishes a custom order or a
    # random order is materialized at draft start.
    draft_position: Mapped[int | None] = mapped_column(nullable=True)

    league = relationship("League", back_populates="teams")
    roster_entries = relationship("RosterEntry", back_populates="team", cascade="all, delete-orphan")

    @property
    def display_name(self) -> str:
        """Resolve generated manager-team labels from the current owner name."""
        if self.owner_name and self.name.endswith("'s Team"):
            return f"{self.owner_name}'s Team"
        return self.name
