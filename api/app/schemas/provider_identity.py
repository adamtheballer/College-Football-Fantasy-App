from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlayerProviderIdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_id: int
    provider: str
    provider_player_id: str
    provider_team_id: str | None = None
    match_confidence: float | None = None
    verification_status: str
    verified_at: datetime | None = None
    verified_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class TeamProviderIdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    provider: str
    provider_team_id: str
    provider_team_name: str | None = None
    created_at: datetime
    updated_at: datetime


class UnmatchedProviderRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    feed: str
    season: int | None = None
    week: int | None = None
    provider_player_id: str | None = None
    provider_team_id: str | None = None
    player_name: str | None = None
    team_name: str | None = None
    dedupe_hash: str
    raw_payload: dict
    status: str
    occurrence_count: int
    last_seen_at: datetime | None = None
    resolved_by_user_id: int | None = None
    resolved_at: datetime | None = None
    mapped_player_id: int | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class UnmatchedProviderRowsList(BaseModel):
    data: list[UnmatchedProviderRowRead]
    total: int
    limit: int
    offset: int


class ProviderRowMappingRequest(BaseModel):
    player_id: int
    match_confidence: float | None = Field(default=1.0, ge=0, le=1)
    reason: str | None = None


class ProviderRowStatusRequest(BaseModel):
    reason: str | None = None


class ProviderReadinessRead(BaseModel):
    provider: str
    season: int
    week: int
    players_total: int
    players_verified_mapped: int
    college_teams_total: int
    college_teams_mapped: int
    open_unmatched_rows: int
    missing_team_mappings: list[str]
    missing_schedule_teams: list[str]
    missing_kickoff_teams: list[str]
    bye_teams: list[str]
    ready: bool


class ProviderIdentityAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int | None = None
    action: str
    provider: str | None = None
    provider_player_id: str | None = None
    provider_team_id: str | None = None
    unmatched_row_id: int | None = None
    actor_user_id: int | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    reason: str | None = None
    created_at: datetime
    updated_at: datetime


UnmatchedStatus = Literal["open", "mapped", "ignored", "resolved"]
