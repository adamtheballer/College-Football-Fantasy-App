from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WaiverClaimCreate(BaseModel):
    team_id: int
    add_player_id: int
    drop_player_id: int | None = None
    bid_amount: int | None = Field(default=None, ge=0)


class WaiverClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    team_id: int
    add_player_id: int
    drop_player_id: int | None = None
    bid_amount: int | None = None
    priority_at_submission: int | None = None
    status: str
    failure_reason: str | None = None
    process_after: datetime
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WaiverClaimList(BaseModel):
    data: list[WaiverClaimRead]
    total: int


class WaiverProcessRequest(BaseModel):
    league_id: int | None = None


class WaiverProcessResult(BaseModel):
    processed: int
    failed: int
    skipped: int
