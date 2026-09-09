from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AdminScheduleSyncRequest(BaseModel):
    season_year: int = Field(ge=2000, le=2100)
    week: int = Field(ge=0, le=20)
    source: Literal["auto", "espn", "sportsdata"] = "auto"
    force_current_week: bool = True


class AdminScheduleSyncResponse(BaseModel):
    season: int
    week: int
    source: str
    games_fetched: int
    games_matched: int
    games_updated: int
    tbd_games_unchanged: int
    games_still_missing_time: int
    skipped_manual_override: int
    skipped_low_confidence: int
    skipped_completed: int
    errors: list[str]
    issues: dict[str, int]
    started_at: datetime
    completed_at: datetime | None = None


class AdminScheduleIssueRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    season: int
    week: int
    team_name: str
    opponent_name: str | None = None
    issue_type: str
    current_value: str | None = None
    provider_value: str | None = None
    source: str
    confidence: float | None = None
    notes: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminScheduleManualOverrideRequest(BaseModel):
    kickoff_at: datetime
    reason: str = Field(min_length=3, max_length=1000)


class AdminScheduleManualOverrideResponse(BaseModel):
    schedule_id: int
    game_id: int | None = None
    kickoff_at: datetime
    time_status: str
    manual_override: bool
    manual_override_reason: str | None = None
