from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SaturdayPickPosition = Literal["QB", "RB", "WR", "TE"]


class SaturdayPickFeaturedPlayerCreate(BaseModel):
    """Verified contest context supplied by the admin who publishes the slate."""

    player_id: int = Field(gt=0)
    opponent: str = Field(min_length=1, max_length=200)
    game_time: datetime
    game_id: int | None = Field(default=None, gt=0)
    projected_points: float | None = Field(default=None, ge=0)


class SaturdayPickContestCreate(BaseModel):
    season: int = Field(ge=2000, le=2100)
    week_number: int = Field(ge=1, le=30)
    contest_position: SaturdayPickPosition
    featured_players: list[SaturdayPickFeaturedPlayerCreate] = Field(min_length=6, max_length=6)
    lock_at: datetime
    title: str = Field(default="Saturday Pick 6", min_length=1, max_length=160)
    sponsor_name: str | None = Field(default=None, max_length=160)
    sponsor_logo_url: str | None = Field(default=None, max_length=500)
    sponsor_offer_text: str | None = Field(default=None, max_length=500)
    sponsor_code: str | None = Field(default=None, max_length=160)
    sponsor_url: str | None = Field(default=None, max_length=500)
    sponsor_terms: str | None = Field(default=None, max_length=1000)


class SaturdayPickContestPublish(BaseModel):
    lock_at: datetime | None = None


class SaturdayPickEntryWrite(BaseModel):
    selected_pick_player_id: int = Field(gt=0)


class SaturdayPickPlayerRead(BaseModel):
    id: int
    player_id: int
    canonical_position: SaturdayPickPosition
    player_name: str
    school: str
    opponent: str
    game_id: int | None = None
    game_time: datetime
    image_url: str | None = None
    projected_points: float | None = None
    live_points: float | None = None
    final_points: float | None = None
    scoring_status: str
    sort_order: int


class SaturdayPickEntryRead(BaseModel):
    id: int
    selected_pick_player_id: int
    submitted_at: datetime
    is_winner: bool
    reward_unlocked_at: datetime | None = None


class SaturdayPickSponsorRead(BaseModel):
    name: str
    logo_url: str | None = None
    offer_text: str | None = None
    terms: str | None = None
    reward_unlocked: bool = False
    code: str | None = None
    url: str | None = None


class SaturdayPickContestRead(BaseModel):
    id: int
    season: int
    week_number: int
    title: str
    contest_position: SaturdayPickPosition
    status: str
    lock_at: datetime
    players: list[SaturdayPickPlayerRead]
    entry: SaturdayPickEntryRead | None = None
    sponsor: SaturdayPickSponsorRead | None = None
