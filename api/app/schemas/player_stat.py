from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlayerStatBase(BaseModel):
    player_id: int
    season: int
    week: int
    source: str
    stats: dict[str, Any]


class PlayerStatRead(PlayerStatBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PlayerStatResponse(BaseModel):
    player_id: int
    season: int
    week: int
    source: str
    cached: bool
    stats: dict[str, Any] | None
    message: str | None = None


class PlayerSeasonTotals(BaseModel):
    games: int
    passing_completions: float
    passing_attempts: float
    passing_yards: float
    passing_tds: float
    interceptions: float
    rushing_attempts: float
    rushing_yards: float
    rushing_tds: float
    receptions: float
    receiving_yards: float
    receiving_tds: float
    field_goals_made: float
    extra_points_made: float
    completion_pct: float | None = None
    yards_per_carry: float | None = None
    yards_per_reception: float | None = None
    fantasy_points: float


class PlayerSeasonSummaryResponse(BaseModel):
    player_id: int
    season: int
    source: str
    totals: PlayerSeasonTotals
    latest_news: str
    latest_news_source_type: str = "generated_stats"
    latest_news_sources: list[str] = Field(default_factory=list)
    latest_news_verified_at: datetime | None = None
    message: str | None = None
