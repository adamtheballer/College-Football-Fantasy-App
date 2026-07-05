from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MockDraftCreate(BaseModel):
    title: str = "Single-Player Mock Draft"
    league_size: int = Field(default=12, ge=2, le=16)
    rounds: int = Field(default=13, ge=1, le=30)
    settings_json: dict = Field(default_factory=dict)


class MockDraftPickCreate(BaseModel):
    player_id: int


class MockDraftPickRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mock_draft_id: int
    player_id: int
    pick_number: int
    round_number: int
    round_pick: int
    team_index: int
    team_name: str
    player_name: str
    player_school: str
    player_position: str
    created_at: datetime
    updated_at: datetime


class MockDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    title: str
    status: str
    league_size: int
    rounds: int
    current_pick: int
    settings_json: dict
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    picks: list[MockDraftPickRead] = []


class MockDraftList(BaseModel):
    data: list[MockDraftRead]
    total: int
