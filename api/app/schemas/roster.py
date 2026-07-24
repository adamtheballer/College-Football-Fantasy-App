from datetime import datetime

from pydantic import BaseModel, ConfigDict

from collegefootballfantasy_api.app.schemas.player import PlayerRead
from collegefootballfantasy_api.app.schemas.transaction import TransactionRead


class RosterEntryBase(BaseModel):
    team_id: int
    player_id: int
    slot: str
    slot_index: int
    status: str


class RosterEntryCreate(BaseModel):
    player_id: int
    slot: str
    slot_index: int | None = None
    status: str


class RosterEntryRead(RosterEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    player: PlayerRead


class RosterSlotRead(BaseModel):
    """A stable configured roster slot with an optional occupied assignment."""

    slot_id: str
    slot_type: str
    slot_index: int
    display_label: str
    is_starter: bool
    is_ir: bool
    id: int | None = None
    team_id: int
    league_id: int
    player_id: int | None = None
    slot: str
    status: str = "EMPTY"
    player: PlayerRead | None = None
    projection: float = 0.0


class RosterEntryList(BaseModel):
    data: list[RosterSlotRead]
    slots: list[RosterSlotRead]
    total: int
    limit: int
    offset: int


class LineupAssignment(BaseModel):
    roster_entry_id: int
    slot: str
    slot_index: int | None = None


class LineupUpdateRequest(BaseModel):
    assignments: list[LineupAssignment]


class LineupUpdateResponse(BaseModel):
    data: list[RosterEntryRead]


class AddDropRequest(BaseModel):
    add_player_id: int
    drop_roster_entry_id: int
    reason: str | None = None


class AddDropResponse(BaseModel):
    roster: list[RosterSlotRead]
    transaction: TransactionRead
