from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


MockDraftStatus = Literal[
    "scheduled",
    "lobby",
    "intermission",
    "live",
    "paused",
    "completed",
    "cancelled",
    "expired",
    "pending_deletion",
]
MockDraftMode = Literal["public_multiplayer", "single_player"]


class MockDraftCreateRequest(BaseModel):
    name: str = Field(default="Mock Draft", min_length=1, max_length=120)
    mode: MockDraftMode = "public_multiplayer"
    team_count: Literal[4, 6, 8, 10, 12] = 12
    round_count: int = Field(default=13, ge=1, le=20)
    pick_timer_seconds: Literal[30, 60, 90, 120] = 90
    scheduled_start_at: datetime
    player_pool: str = Field(default="power4", min_length=1, max_length=60)
    scoring_type: str = Field(default="espn_full_ppr", min_length=1, max_length=80)
    bot_difficulty: str = Field(default="basic", min_length=1, max_length=60)

    @field_validator("scheduled_start_at")
    @classmethod
    def scheduled_start_must_be_future(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if value.astimezone(timezone.utc) <= now:
            raise ValueError("scheduled_start_at must be in the future")
        return value


class MockDraftSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    team_count: Literal[4, 6, 8, 10, 12] | None = None
    round_count: int | None = Field(default=None, ge=1, le=20)
    pick_timer_seconds: Literal[30, 60, 90, 120] | None = None
    scheduled_start_at: datetime | None = None
    player_pool: str | None = Field(default=None, min_length=1, max_length=60)
    scoring_type: str | None = Field(default=None, min_length=1, max_length=80)
    bot_difficulty: str | None = Field(default=None, min_length=1, max_length=60)


class MockDraftCreateResponse(BaseModel):
    mock_draft_id: int
    id: int
    mode: MockDraftMode
    invite_code: str | None = None
    invite_link: str | None = None
    join_url: str | None = None
    lobby_url: str
    status: MockDraftStatus
    scheduled_start_at: datetime


class MockDraftJoinRequest(BaseModel):
    invite_code: str = Field(min_length=6, max_length=256)
    team_name: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)


class MockDraftParticipantRead(BaseModel):
    id: int
    mock_draft_id: int
    user_id: int | None = None
    display_name: str
    team_name: str
    participant_type: Literal["human", "bot"]
    seat_number: int
    draft_position: int | None = None
    is_host: bool
    is_ready: bool
    joined_at: datetime
    left_at: datetime | None = None
    last_seen_at: datetime | None = None
    connection_status: str
    auto_pick_count: int


class MockDraftSessionSummary(BaseModel):
    id: int
    name: str
    mode: MockDraftMode
    invite_code: str | None = None
    status: MockDraftStatus
    team_count: int
    round_count: int
    draft_type: str
    pick_timer_seconds: int
    scheduled_start_at: datetime
    intermission_started_at: datetime | None = None
    intermission_ends_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    player_pool: str
    scoring_type: str
    bot_difficulty: str
    draft_order_locked: bool
    should_preserve_history: bool


class MockDraftLobbyRead(BaseModel):
    session: MockDraftSessionSummary
    participants: list[MockDraftParticipantRead] = Field(default_factory=list)
    invite_code: str | None = None
    invite_link: str | None = None
    join_url: str | None = None
    server_time: datetime
    seconds_until_start: int
    is_current_user_host: bool
    settings_locked: bool
    can_join: bool
    can_leave: bool
    can_edit_settings: bool
    can_start_now: bool = False
    message: str

    id: int
    name: str
    status: MockDraftStatus
    team_count: int
    manager_count: int
    joined_count: int
    can_enter_room: bool
    scheduled_start_at: datetime


class MockDraftPickCreate(BaseModel):
    player_id: int


class MockDraftAutoPickRequest(BaseModel):
    force: bool = False
    expected_overall_pick: int | None = Field(default=None, ge=1)


class MockDraftPickRead(BaseModel):
    id: int
    mock_draft_id: int
    participant_id: int
    participant_name: str
    team_name: str
    player_id: int
    player_name: str
    player_position: str
    player_school: str
    overall_pick: int
    round_number: int
    round_pick: int
    pick_source: Literal["human", "bot", "auto_timer", "host_override", "system"]
    auto_pick_reason: str | None = None
    made_by_user_id: int | None = None
    created_at: datetime


class MockDraftRosterRead(BaseModel):
    participant_id: int
    participant_name: str
    team_name: str
    picks: list[MockDraftPickRead] = Field(default_factory=list)


class MockDraftRoomRead(BaseModel):
    session: MockDraftSessionSummary
    server_time: datetime
    participants: list[MockDraftParticipantRead] = Field(default_factory=list)
    picks: list[MockDraftPickRead] = Field(default_factory=list)
    rosters: list[MockDraftRosterRead] = Field(default_factory=list)
    draft_order: list[int] = Field(default_factory=list)
    current_overall_pick: int
    current_round: int
    current_round_pick: int
    current_participant_id: int | None = None
    current_participant_name: str | None = None
    current_participant_type: str | None = None
    current_team_name: str | None = None
    current_pick_started_at: datetime | None = None
    current_pick_expires_at: datetime | None = None
    seconds_remaining: int | None = None
    total_picks: int
    is_user_on_clock: bool
    is_complete: bool
    can_exit: bool
    email_history_available: bool
    should_show_email_prompt: bool
    available_player_count: int

    mock_draft_id: int
    status: MockDraftStatus
    pick_timer_seconds: int
    total_rounds: int
    current_pick: int
    current_team_id: int | None = None
    user_team_id: int | None = None
    can_make_pick: bool
    phase_type: str | None = None


class MockDraftHistoryRead(BaseModel):
    mock_draft_id: int
    draft_name: str
    completed_at: datetime | None = None
    participants: list[MockDraftParticipantRead] = Field(default_factory=list)
    draft_order: list[MockDraftParticipantRead] = Field(default_factory=list)
    picks: list[MockDraftPickRead] = Field(default_factory=list)
    picks_by_round: list[dict] = Field(default_factory=list)
    rosters: list[MockDraftRosterRead] = Field(default_factory=list)
    plain_text: str
    html: str
    pick_count: int


class MockDraftEmailHistoryRequest(BaseModel):
    send_to_account_email: bool = True


class MockDraftEmailHistoryResponse(BaseModel):
    sent: bool
    emails: list[str] = Field(default_factory=list)
    message: str
    history: MockDraftHistoryRead | None = None


class MockDraftExitResponse(BaseModel):
    ok: bool
    navigate_to: str = "/draft"


class MockDraftRecentList(BaseModel):
    data: list[MockDraftLobbyRead] = Field(default_factory=list)


class MockDraftJoinByCodeRequest(BaseModel):
    invite_code: str


class MockDraftLobbyReadyRequest(BaseModel):
    ready: bool
