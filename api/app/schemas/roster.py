from datetime import datetime

from pydantic import BaseModel, ConfigDict

from collegefootballfantasy_api.app.schemas.player import PlayerRead


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
