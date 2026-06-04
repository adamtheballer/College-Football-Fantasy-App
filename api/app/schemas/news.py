from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NewsItemRead(BaseModel):
    id: int
    title: str
    summary: str | None = None
    category: str
    source_name: str
    source_url: str
    published_at: datetime | None = None
    player_id: int | None = None
    player_name_raw: str | None = None
    team_name_raw: str | None = None
    canonical_team: str | None = None
    position: str | None = None
    confidence_score: float
    fantasy_relevance_score: float
    fantasy_impact: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_breaking: bool = False


class NewsListResponse(BaseModel):
    data: list[NewsItemRead]
    total: int
    limit: int
    offset: int


class NewsSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    url: str
    active: bool
    priority: int
    poll_interval_minutes: int
    last_polled_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None


class NewsSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: str = Field(default="manual", min_length=1, max_length=30)
    url: str = Field(min_length=1, max_length=600)
    active: bool = True
    priority: int = 50
    poll_interval_minutes: int = Field(default=60, ge=5, le=24 * 60)


class NewsIngestRunResponse(BaseModel):
    sources_checked: int = 0
    rows_seen: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    duplicates_skipped: int = 0
    low_relevance_skipped: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)


class ManualNewsCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    category: str = "general"
    source_name: str = Field(default="Manual", min_length=1, max_length=120)
    source_url: str = Field(min_length=1, max_length=900)
    published_at: datetime | None = None
    player_id: int | None = None
    player_name_raw: str | None = Field(default=None, max_length=200)
    team_name_raw: str | None = Field(default=None, max_length=200)
    fantasy_impact: str | None = None
    tags: list[str] = Field(default_factory=list)


def is_breaking_news(published_at: datetime | None, *, now: datetime | None = None) -> bool:
    if not published_at:
        return False
    now = now or datetime.now(timezone.utc)
    published = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    return (now - published.astimezone(timezone.utc)).total_seconds() <= 72 * 3600
