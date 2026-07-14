from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WaiverClaimCreate(BaseModel):
    add_player_id: int = Field(gt=0)
    drop_roster_entry_id: int | None = Field(default=None, gt=0)
    faab_bid: int = Field(default=0, ge=0)
    reason: str | None = Field(default=None, max_length=500)


class WaiverClaimCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class WaiverClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    fantasy_team_id: int
    add_player_id: int
    add_player_name: str
    drop_player_id: int | None = None
    drop_player_name: str | None = None
    priority: int | None = None
    faab_bid: int = 0
    status: str
    failure_reason: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class WaiverDropCandidateRead(BaseModel):
    roster_entry_id: int
    player_id: int
    player_name: str
    position: str | None = None
    school: str | None = None
    slot: str


class WaiverProcessResponse(BaseModel):
    processed: int
    failed: int
    pending: int
