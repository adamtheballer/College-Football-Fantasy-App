from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LineupEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lineup_id: int
    roster_entry_id: int | None = None
    player_id: int
    player_name: str | None = None
    player_position: str | None = None
    player_school: str | None = None
    slot: str
    is_starter: bool


class LineupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    team_id: int
    season: int
    week: int
    status: str
    locked_at: datetime | None = None
    entries: list[LineupEntryRead]


class LineupAssignment(BaseModel):
    roster_entry_id: int | None = None
    player_id: int
    slot: str
    is_starter: bool


class LineupUpdateRequest(BaseModel):
    assignments: list[LineupAssignment]


class LineupUpdateResponse(BaseModel):
    data: LineupRead
