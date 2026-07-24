from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, event, func, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class RosterEntry(TimestampMixin, Base):
    __tablename__ = "roster_entries"
    __table_args__ = (
        UniqueConstraint("team_id", "player_id", name="uq_roster_team_player"),
        UniqueConstraint("league_id", "player_id", name="uq_roster_league_player"),
        UniqueConstraint("team_id", "slot", "slot_index", name="uq_roster_team_slot_index"),
        Index("ix_roster_entries_league_id", "league_id"),
        Index("ix_roster_entries_league_player", "league_id", "player_id"),
        Index("ix_roster_entries_team_id", "team_id"),
        Index("ix_roster_entries_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    slot: Mapped[str] = mapped_column(String(50))
    slot_index: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(50))

    team = relationship("Team", back_populates="roster_entries")
    player = relationship("Player", back_populates="roster_entries")


@event.listens_for(Session, "before_flush")
def assign_missing_roster_slot_indexes(
    session: Session,
    _flush_context: object,
    _instances: object,
) -> None:
    """Keep legacy direct writers compatible while production services assign slots explicitly."""
    pending_by_slot: dict[tuple[int, str], int] = {}
    candidates = sorted(
        (
            entry
            for entry in (*session.new, *session.dirty)
            if isinstance(entry, RosterEntry)
            and entry.team_id is not None
            and entry.slot
            and (
                entry.slot_index is None
                or (
                    entry in session.dirty
                    and inspect(entry).attrs.slot.history.has_changes()
                    and not inspect(entry).attrs.slot_index.history.has_changes()
                )
            )
        ),
        key=lambda entry: (entry.team_id, entry.slot, entry.player_id or 0),
    )
    for entry in candidates:
        key = (entry.team_id, entry.slot)
        if key not in pending_by_slot:
            max_slot_index = select(func.max(RosterEntry.slot_index)).where(
                RosterEntry.team_id == entry.team_id,
                RosterEntry.slot == entry.slot,
            )
            if entry.id is not None:
                max_slot_index = max_slot_index.where(RosterEntry.id != entry.id)
            existing_max = session.scalar(max_slot_index)
            pending_by_slot[key] = int(existing_max or 0)
        pending_by_slot[key] += 1
        entry.slot_index = pending_by_slot[key]
