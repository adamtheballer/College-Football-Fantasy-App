from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WaiverClaimCreate(BaseModel):
    team_id: int | None = Field(default=None, gt=0)
    fantasy_team_id: int | None = Field(default=None, gt=0)
    add_player_id: int = Field(gt=0)
    drop_roster_entry_id: int | None = Field(default=None, gt=0)
    faab_bid: int = Field(default=0, ge=0)
    preference_order: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=500)


class WaiverClaimCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class WaiverClaimReorder(BaseModel):
    claim_ids: list[int] = Field(min_length=1)


class FreeAgentAdd(BaseModel):
    team_id: int | None = Field(default=None, gt=0)
    fantasy_team_id: int | None = Field(default=None, gt=0)
    drop_roster_entry_id: int | None = Field(default=None, gt=0)


class WaiverClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    team_id: int
    fantasy_team_id: int
    add_player_id: int
    add_player_name: str
    drop_roster_entry_id: int | None = None
    drop_player_id: int | None = None
    drop_player_name: str | None = None
    priority: int | None = None
    faab_bid: int = 0
    status: str
    failure_reason: str | None = None
    failure_code: str | None = None
    season: int
    processing_week: int
    processing_window_id: str
    waiver_period_id: int
    processing_run_id: int | None = None
    preference_order: int
    winning_bid: int | None = None
    prior_priority: int | None = None
    resulting_priority: int | None = None
    process_after: datetime | None = None
    created_at: datetime
    updated_at: datetime
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


class FreeAgentAddRead(BaseModel):
    team_id: int
    player_id: int
    player_name: str
    roster_entry_id: int
    slot: str
    slot_index: int
    transaction_id: int
