from datetime import datetime

from pydantic import BaseModel


class WaiverClaimCreateRequest(BaseModel):
    team_id: int
    add_player_id: int
    drop_player_id: int | None = None
    bid_amount: int | None = None
    note: str | None = None


class WaiverClaimRead(BaseModel):
    id: int
    league_id: int
    team_id: int
    team_name: str | None = None
    add_player_id: int
    add_player_name: str | None = None
    drop_player_id: int | None = None
    drop_player_name: str | None = None
    bid_amount: int
    note: str | None = None
    priority_snapshot: int | None = None
    status: str
    process_batch_key: str | None = None
    processed_reason: str | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WaiverClaimList(BaseModel):
    data: list[WaiverClaimRead]
    total: int
    limit: int
    offset: int


class WaiverProcessRequest(BaseModel):
    batch_key: str | None = None


class WaiverProcessResultRow(BaseModel):
    claim_id: int
    team_id: int
    team_name: str | None = None
    add_player_id: int
    add_player_name: str | None = None
    bid_amount: int
    status: str
    reason: str | None = None


class WaiverProcessResponse(BaseModel):
    batch_key: str
    processed_count: int
    won_count: int
    lost_count: int
    invalid_count: int
    data: list[WaiverProcessResultRow]
