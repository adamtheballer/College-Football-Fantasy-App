from datetime import datetime

from pydantic import BaseModel, ConfigDict

from collegefootballfantasy_api.app.schemas.player import PlayerRead
from collegefootballfantasy_api.app.schemas.transaction import TransactionRead


class RosterEntryBase(BaseModel):
    team_id: int
    player_id: int
    slot: str
    status: str


class RosterEntryCreate(BaseModel):
    player_id: int
    slot: str
    status: str


class RosterEntryRead(RosterEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    player: PlayerRead


class RosterEntryList(BaseModel):
    data: list[RosterEntryRead]
    total: int
    limit: int
    offset: int


class LineupAssignment(BaseModel):
    roster_entry_id: int
    slot: str


class LineupUpdateRequest(BaseModel):
    assignments: list[LineupAssignment]


class LineupUpdateResponse(BaseModel):
    data: list[RosterEntryRead]


class AddDropRequest(BaseModel):
    add_player_id: int
    drop_roster_entry_id: int
    reason: str | None = None


class AddDropResponse(BaseModel):
    roster: list[RosterEntryRead]
    transaction: TransactionRead
