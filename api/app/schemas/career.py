from datetime import datetime

from pydantic import BaseModel, Field


class CareerRecordRead(BaseModel):
    wins: int = 0
    losses: int = 0
    ties: int = 0
    win_pct: float = 0.0


class CareerProfileRead(BaseModel):
    user_id: int
    display_name: str
    username: str | None = None
    member_since: datetime
    record: CareerRecordRead
    leagues: dict[str, int]
    drafts: dict[str, int]
    trades: dict[str, int]
    waivers: dict[str, int]
    postseason: dict[str, int]
    matchups: dict[str, int]
    scoring: dict[str, float | None]
    streaks: dict[str, int]
    rivalry: dict[str, int]


class CareerPublicProfileRead(BaseModel):
    """Authenticated-viewer-safe subset of a user's career résumé."""

    user_id: int
    display_name: str
    username: str | None = None
    member_since: datetime
    record: CareerRecordRead
    leagues: dict[str, int]
    drafts: dict[str, int]
    trades: dict[str, int]
    postseason: dict[str, int]


class CareerEventRead(BaseModel):
    id: int
    event_type: str
    title: str
    season: int | None = None
    week: int | None = None
    league_id: int | None = None
    occurred_at: datetime
    metadata: dict = Field(default_factory=dict)


class CareerEventsRead(BaseModel):
    data: list[CareerEventRead]
    total: int


class CareerLeagueRead(BaseModel):
    league_id: int
    name: str
    season: int
    status: str
    record: CareerRecordRead
    points_for: float
    final_place: int | None = None
    postseason_result: str | None = None
    rival_team_name: str | None = None
    rival_record: CareerRecordRead | None = None


class CareerLeaguesRead(BaseModel):
    data: list[CareerLeagueRead]


class CareerTrophyRead(BaseModel):
    key: str
    title: str
    season: int | None = None
    league_id: int | None = None
    subtitle: str | None = None


class CareerTrophiesRead(BaseModel):
    data: list[CareerTrophyRead]


class RivalCandidateRead(BaseModel):
    team_id: int
    team_name: str
    manager_name: str


class RivalryRead(BaseModel):
    league_id: int
    season: int
    team_id: int
    rival_team_id: int | None = None
    rival_team_name: str | None = None
    rival_manager_name: str | None = None
    selected_at: datetime | None = None
    changed_at: datetime | None = None
    can_change: bool = True
    candidates: list[RivalCandidateRead]


class RivalryUpdate(BaseModel):
    rival_team_id: int


class RivalryMatchupRead(BaseModel):
    matchup_id: int
    is_rivalry_matchup: bool
    is_championship: bool
    user_team_name: str
    rival_team_name: str | None = None
    series: CareerRecordRead
    last_meeting: dict | None = None
