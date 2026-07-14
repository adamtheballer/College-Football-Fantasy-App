from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminReasonMixin(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("reason must describe the admin action")
        return normalized


class AdminRerunScoringRequest(AdminReasonMixin):
    league_id: int | None = Field(default=None, gt=0)
    season: int = Field(ge=2000, le=2100)
    week: int = Field(ge=1, le=20)
    provider: str = Field(default="admin")


class AdminCorrectionRequest(AdminReasonMixin):
    player_id: int = Field(gt=0)
    season: int = Field(ge=2000, le=2100)
    week: int = Field(ge=1, le=20)
    stats: dict[str, Any]


class AdminReconcilePlayerWeekRequest(AdminReasonMixin):
    player_id: int = Field(gt=0)
    season: int = Field(ge=2000, le=2100)
    week: int = Field(ge=1, le=20)
    league_id: int | None = Field(default=None, gt=0)


class AdminReconcileLeagueWeekRequest(AdminReasonMixin):
    league_id: int = Field(gt=0)
    season: int = Field(ge=2000, le=2100)
    week: int = Field(ge=1, le=20)


class AdminWeekStatusRequest(AdminReasonMixin):
    league_id: int = Field(gt=0)
    season: int = Field(ge=2000, le=2100)
    week: int = Field(ge=1, le=20)


class ScoringSummaryRead(BaseModel):
    players_scored: int
    teams_scored: int
    matchups_updated: int
    standings_updated: int


class ScoringRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int | None = None
    season: int
    week: int
    provider: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    players_updated: int
    teams_updated: int
    matchups_updated: int
    error_message: str | None = None


class ScoringRunsList(BaseModel):
    data: list[ScoringRunRead]
    total: int
    limit: int
    offset: int


class ProviderHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    feed: str
    scope_key: str
    status: str
    last_attempted_at: datetime | None = None
    last_success_at: datetime | None = None
    expires_at: datetime | None = None
    error_message: str | None = None
    consecutive_failures: int


class ProviderHealthResponse(BaseModel):
    sync_states: list[ProviderHealthRead]
    open_unmatched_rows: int
    failed_scoring_runs: int


class CorrectionPreviewResponse(BaseModel):
    player_id: int
    season: int
    week: int
    affected_league_ids: list[int]
    before_stats: dict | None = None
    after_stats: dict
    before_scores: dict[int, float | None]
    projected_scores: dict[int, float]


class AdminScoringAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    actor_user_id: int | None = None
    league_id: int | None = None
    season: int | None = None
    week: int | None = None
    player_id: int | None = None
    affected_league_ids: list[int] | None = None
    reason: str
    before_state: dict | None = None
    after_state: dict | None = None
    created_at: datetime
    updated_at: datetime


class AdminActionResponse(BaseModel):
    action: str
    status: Literal["success"]
    message: str
    audit: AdminScoringAuditRead
    summary: ScoringSummaryRead | None = None
    preview: CorrectionPreviewResponse | None = None
