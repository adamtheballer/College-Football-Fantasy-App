from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SaturdayPickPosition = Literal["QB", "RB", "WR", "TE"]


class SaturdayPickContestCreate(BaseModel):
    season: int = Field(ge=2000, le=2100)
    week_number: int = Field(ge=1, le=30)
    contest_position: SaturdayPickPosition
    featured_player_ids: list[int]
    lock_at: datetime | None = None
    title: str = "Saturday Pick 6"
    scoring_policy_version: str = "STANDARD_V1"
    sponsor_name: str | None = None
    sponsor_logo_url: str | None = None
    sponsor_offer_text: str | None = None
    sponsor_code: str | None = None
    sponsor_url: str | None = None
    sponsor_terms: str | None = None
    position_overridden: bool = False
    override_reason: str | None = None


class SaturdayPickContestPublish(BaseModel):
    lock_at: datetime | None = None


class SaturdayPickEntryWrite(BaseModel):
    selected_pick_player_id: int


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
    scoring_policy_version: str
    winning_player_ids: list[int] = []
    position_overridden: bool
    override_reason: str | None = None
    published_at: datetime | None = None
    locked_at: datetime | None = None
    finalized_at: datetime | None = None
    players: list[SaturdayPickPlayerRead]
    entry: SaturdayPickEntryRead | None = None
    sponsor: SaturdayPickSponsorRead | None = None


class SaturdayPickRotationRead(BaseModel):
    default_rotation: list[SaturdayPickPosition]
    recommended_position: SaturdayPickPosition
