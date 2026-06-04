from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LeagueAutomationJobScheduleRequest(BaseModel):
    job_type: Literal["waiver_process", "week_scores_recompute"]
    run_at: datetime | None = None
    payload: dict = Field(default_factory=dict)
    max_attempts: int = 3


class LeagueAutomationJobRead(BaseModel):
    id: int
    league_id: int
    job_type: str
    status: str
    run_at: datetime
    payload: dict
    attempts: int
    max_attempts: int
    locked_by: str | None = None
    locked_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    last_error: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class LeagueAutomationJobList(BaseModel):
    data: list[LeagueAutomationJobRead]
    total: int
    limit: int
    offset: int


class LeagueAutomationRunDueRequest(BaseModel):
    limit: int = 20


class LeagueAutomationRunDueResultRow(BaseModel):
    job_id: int
    job_type: str
    status: str
    detail: str | None = None


class LeagueAutomationRunDueResponse(BaseModel):
    worker_id: str
    processed: int
    completed: int
    failed: int
    results: list[LeagueAutomationRunDueResultRow]
