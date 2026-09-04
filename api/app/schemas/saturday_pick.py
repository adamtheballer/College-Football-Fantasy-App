from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from collegefootballfantasy_api.app.core.config import settings


SaturdayPickPosition = Literal["QB", "RB", "WR", "TE"]


class SaturdayPickContestCreate(BaseModel):
    season: int = Field(ge=2000, le=2100)
    week_number: int = Field(ge=1, le=30)
    contest_position: SaturdayPickPosition
    featured_player_ids: list[int]
    lock_at: datetime | None = None
    title: str = Field(default="Saturday Pick 6", min_length=1, max_length=120)
    scoring_policy_version: str = Field(default="STANDARD_V1", max_length=80)
    sponsor_name: str | None = Field(default=None, max_length=120)
    sponsor_logo_url: str | None = Field(default=None, max_length=500)
    sponsor_offer_text: str | None = Field(default=None, max_length=500)
    sponsor_code: str | None = Field(default=None, max_length=100)
    sponsor_url: str | None = Field(default=None, max_length=500)
    sponsor_terms: str | None = Field(default=None, max_length=1000)
    position_overridden: bool = False
    override_reason: str | None = Field(default=None, max_length=500)


class SaturdayPickContestPublish(BaseModel):
    lock_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=1000)


class SaturdayPickContestPrepare(BaseModel):
    season: int = Field(ge=2000, le=2100)
    week_number: int = Field(ge=1, le=30)
    reason: str | None = Field(default=None, max_length=1000)


class SaturdayPickContestReviewUpdate(BaseModel):
    featured_player_ids: list[int] = Field(min_length=6, max_length=6)
    title: str = Field(default="Saturday Pick 6", min_length=1, max_length=120)
    sponsor_name: str | None = Field(default=None, max_length=120)
    sponsor_logo_url: str | None = Field(default=None, max_length=500)
    sponsor_offer_text: str | None = Field(default=None, max_length=500)
    sponsor_code: str | None = Field(default=None, max_length=100)
    sponsor_url: str | None = Field(default=None, max_length=500)
    sponsor_terms: str | None = Field(default=None, max_length=1000)
    reason: str = Field(min_length=3, max_length=1000)


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

    @field_serializer("image_url")
    def serialize_player_image_url(self, value: str | None) -> str | None:
        """Never expose third-party player portraits while beta compliance is active."""
        return value if settings.player_headshots_enabled else None


class SaturdayPickLockPlayerRead(BaseModel):
    id: int
    player_id: int
    player_name: str
    opponent: str
    game_time: datetime


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
    first_game_player: SaturdayPickLockPlayerRead
    players: list[SaturdayPickPlayerRead]
    entry: SaturdayPickEntryRead | None = None
    sponsor: SaturdayPickSponsorRead | None = None


class SaturdayPickRotationRead(BaseModel):
    default_rotation: list[SaturdayPickPosition]
    recommended_position: SaturdayPickPosition


class SaturdayPickCandidateRead(BaseModel):
    player_id: int
    player_name: str
    school: str
    position: SaturdayPickPosition
    opponent: str
    kickoff_at: datetime
    projected_points: float


class SaturdayPickContentAuditRead(BaseModel):
    id: int
    action: str
    reason: str | None = None
    actor_user_id: int | None = None
    created_at: datetime


class SaturdayPickAdminReviewRead(BaseModel):
    contest: SaturdayPickContestRead | None = None
    candidates: list[SaturdayPickCandidateRead] = []
    sponsor_draft: dict[str, str | None] | None = None
    audit: list[SaturdayPickContentAuditRead] = []
