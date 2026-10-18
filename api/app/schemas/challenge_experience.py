from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from collegefootballfantasy_api.app.schemas.challenge_primitives import (
    StrictModel,
    Selection,
    Participant,
    GameRead,
)

ExperienceKind = Literal["fanwars", "millionaire", "creator", "survivor"]


class CreatorWrite(StrictModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    logo_url: str | None = Field(default=None, max_length=350 * 1024)
    links: dict[str, str] = Field(default_factory=dict, max_length=5)
    authorized: bool = False
    active: bool = False
    owner_user_id: int | None = Field(default=None, gt=0)

    @field_validator("logo_url")
    @classmethod
    def approved_asset(cls, value):
        if value and value.startswith("data:image/jpeg;base64,"):
            from .auth import UserProfileUpdate

            return UserProfileUpdate(avatar_url=value).avatar_url
        if value and value.startswith("data:image/png;base64,"):
            import base64, binascii

            try:
                raw = base64.b64decode(value.split(",", 1)[1], validate=True)
            except (ValueError, binascii.Error):
                raise ValueError("Invalid PNG image data.") from None
            if len(raw) > 250 * 1024 or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Use a valid PNG of 250 KB or less.")
            return value
        if value and (
            not value.startswith("/assets/")
            or ".." in value
            or "?" in value
            or "#" in value
        ):
            raise ValueError("Use an approved asset under /assets/.")
        return value

    @field_validator("links")
    @classmethod
    def secure_links(cls, links):
        from urllib.parse import urlparse

        for label, url in links.items():
            u = urlparse(url)
            if (
                not label
                or len(label) > 40
                or u.scheme != "https"
                or not u.hostname
                or u.username
                or u.password
                or len(url) > 500
            ):
                raise ValueError(
                    "Platform links must be public HTTPS URLs without credentials."
                )
        return links


class CreatorRead(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    logo_url: str | None
    links: dict[str, str]
    authorized: bool
    active: bool


class SeriesWrite(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    season: int = Field(ge=2000, le=2100)
    start_week: int = Field(ge=1, le=15)
    end_week: int = Field(ge=1, le=15)
    entry_open_at: datetime
    first_lock_at: datetime


class SeriesRead(SeriesWrite):
    id: int
    active: bool


class ExperienceCreate(StrictModel):
    season: int = Field(ge=2000, le=2100)
    week: int = Field(ge=1, le=15)
    kind: ExperienceKind
    creator_id: int | None = Field(default=None, gt=0)
    series_id: int | None = Field(default=None, gt=0)
    entry_open_at: datetime


class SalaryWrite(StrictModel):
    player_id: int = Field(gt=0)
    salary: float = Field(gt=0, le=100, allow_inf_nan=False, multiple_of=0.01)


class ExperienceConfig(StrictModel):
    expected_version: int = Field(ge=0)
    game_ids: list[int] = Field(default_factory=list, max_length=12)
    player_ids: list[int] = Field(default_factory=list, max_length=1500)
    salaries: list[SalaryWrite] = Field(default_factory=list, max_length=1500)
    creator_picks: list[Selection] = Field(default_factory=list, max_length=10)
    correct_points: int = Field(default=10, ge=1, le=100)
    minimum_fans: int = Field(default=3, ge=2, le=1000)
    rivalries: list[tuple[int, int]] = Field(default_factory=list, max_length=10)


class SchoolRead(BaseModel):
    id: int
    name: str
    conference: str


class AllegianceWrite(StrictModel):
    school_id: int = Field(gt=0)


class SchoolStanding(BaseModel):
    school_id: int
    school: str
    conference: str
    rank: int | None
    fan_points: float
    accuracy: float | None
    correct_picks: int
    eligible_picks: int
    active_fans: int
    provisional: bool


class SurvivorPickRead(BaseModel):
    week: int
    team: str | None
    opponent: str | None
    outcome: str
    game: GameRead | None


class ExperienceRead(BaseModel):
    season: int
    week: int
    locked_game_ids: list[int] = Field(default_factory=list)
    projections: dict[int, float] = Field(default_factory=dict)
    enabled: bool
    kind: ExperienceKind
    entry_open_at: datetime
    participants: int
    creator: CreatorRead | None = None
    creator_picks: list[Selection] | None = None
    creator_correct: int | None = None
    creator_score: float | None = None
    comparison: (
        Literal["BEAT THE CREATOR", "TIED THE CREATOR", "CREATOR WON"] | None
    ) = None
    salary_budget: int = 100
    salaries: list[SalaryWrite] = Field(default_factory=list)
    correct_points: int = 10
    minimum_fans: int = 3
    schools: list[SchoolRead] = Field(default_factory=list)
    allegiance: SchoolRead | None = None
    your_points: float | None = None
    your_rank: int | None = None
    best_performer: str | None = None
    player_points: dict[int, float] = Field(default_factory=dict)
    personal_contribution: float | None = None
    personal_correct: int | None = None
    school_week_rank: int | None = None
    school_season_rank: int | None = None
    school_standings: list[SchoolStanding] = Field(default_factory=list)
    rivalries: list[dict] = Field(default_factory=list)
    series: SeriesRead | None = None
    survivor_status: str | None = None
    weeks_survived: int = 0
    remaining_survivors: int = 0
    eliminated: int = 0
    previous_picks: list[SurvivorPickRead] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)


class ModeRead(BaseModel):
    lock_at: datetime | None
    server_now: datetime
    kind: ExperienceKind
    name: str
    description: str
    competitions: list[int]
    participants: int
    state: str


class ExperienceStanding(Participant):
    rank: int
    points: float | None
    status: str
    correct_picks: int | None = None
    selections: list[Selection] | None = None


class ExperienceLeaderboard(BaseModel):
    challenge_id: int
    kind: ExperienceKind
    unit: str
    provisional: bool
    total: int
    data: list[ExperienceStanding]
    your_rank: ExperienceStanding | None
    school_standings: list[SchoolStanding] = Field(default_factory=list)


class DecisionWrite(StrictModel):
    expected_version: int = Field(ge=0)
    game_id: int = Field(gt=0)
    reason: str = Field(min_length=10, max_length=500)


class CreatorCorrection(StrictModel):
    expected_version: int = Field(ge=0)
    picks: list[Selection] = Field(min_length=10, max_length=10)
    reason: str = Field(min_length=10, max_length=500)


class VisibilityWrite(StrictModel):
    expected_version: int = Field(ge=0)
    enabled: bool
    reason: str = Field(min_length=5, max_length=500)


class EventWrite(StrictModel):
    challenge_id: int | None = Field(default=None, gt=0)
    creator_slug: str | None = Field(default=None, max_length=80)
    event_type: Literal["view", "share", "referral_open"]


class AnalyticsRead(BaseModel):
    challenge_id: int
    views: int
    shares: int
    unique_participants: int
    submitted_entries: int
    completion_rate: float
    returning_participants: int
    creator_link_visitors: int
    attributed_signups: int


class RecentResultRead(BaseModel):
    challenge_id: int
    kind: str
    name: str
    season: int
    week: int
    raw_points: float | None
    rank: int | None
    status: str


class SalarySuggestionRead(SalaryWrite):
    projection: float
    rule: str


class AnalyticsPreference(StrictModel):
    enabled: bool
