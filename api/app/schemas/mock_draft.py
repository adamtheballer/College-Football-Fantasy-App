from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from collegefootballfantasy_api.app.schemas.draft_room import (
    DraftEventEnvelopeRead,
    DraftPositionEligibilityRead,
    DraftQueueItemRead,
    DraftRoomPickRead,
    DraftRoomTeamRead,
    DraftRosterTeamRead,
)


class MockDraftCreateRequest(BaseModel):
    manager_count: Literal[4, 6, 8, 10, 12] = 12
    pick_timer_seconds: int = Field(default=90, ge=15, le=300)
    name: str = "Mock Draft"
    mode: Literal["public_multiplayer", "single_player"] = "public_multiplayer"


class MockDraftSeatRead(BaseModel):
    id: int
    seat_number: int
    name: str
    owner_name: str | None = None
    owner_user_id: int | None = None
    is_cpu: bool = False
    lobby_joined: bool = False
    lobby_connected: bool = False
    lobby_ready: bool = False


class MockDraftSessionRead(BaseModel):
    id: int
    name: str
    invite_code: str
    mode: Literal["public_multiplayer", "single_player"] = "public_multiplayer"
    status: str
    manager_count: int
    pick_timer_seconds: int
    draft_type: str
    commissioner_user_id: int
    roster_slots: dict[str, int]
    scoring_json: dict = Field(default_factory=dict)
    seats: list[MockDraftSeatRead] = Field(default_factory=list)
    joined_count: int = 0
    connected_count: int = 0
    ready_count: int = 0
    user_seat_id: int | None = None
    seconds_remaining: int | None = None
    can_enter_room: bool = False
    created_at: datetime
    updated_at: datetime


class MockDraftPreviewRead(BaseModel):
    id: int
    name: str
    invite_code: str
    mode: Literal["public_multiplayer", "single_player"] = "public_multiplayer"
    status: str
    manager_count: int
    joined_count: int
    pick_timer_seconds: int


class MockDraftJoinByCodeRequest(BaseModel):
    invite_code: str


class MockDraftStatusUpdateRequest(BaseModel):
    status: Literal["lobby_open", "countdown", "active", "paused", "abandoned"]


class MockDraftLobbyReadyRequest(BaseModel):
    ready: bool


class MockDraftPickCreate(BaseModel):
    player_id: int


class MockDraftQueueRead(BaseModel):
    session_id: int
    seat_id: int
    count: int
    data: list[DraftQueueItemRead] = Field(default_factory=list)


class MockDraftQueueAddRequest(BaseModel):
    player_id: int


class MockDraftQueueReorderRequest(BaseModel):
    player_ids: list[int] = Field(default_factory=list)


class MockDraftRoomRead(BaseModel):
    draft_room_id: int
    mock_draft_id: int
    mode: Literal["public_multiplayer", "single_player"] = "public_multiplayer"
    status: str
    draft_status: Literal["waiting", "active", "paused", "complete"]
    pick_timer_seconds: int
    total_rounds: int
    total_picks: int
    roster_slots: dict[str, int]
    position_eligibility: dict[str, DraftPositionEligibilityRead] = Field(default_factory=dict)
    draft_order: list[int] = Field(default_factory=list)
    drafted_player_ids: list[int] = Field(default_factory=list)
    available_player_count: int = 0
    rosters_by_team: list[DraftRosterTeamRead] = Field(default_factory=list)
    lobby_ready_count: int = 0
    lobby_joined_count: int = 0
    lobby_connected_count: int = 0
    teams: list[DraftRoomTeamRead] = Field(default_factory=list)
    picks: list[DraftRoomPickRead] = Field(default_factory=list)
    current_pick: int
    current_round: int
    current_round_pick: int
    current_team_id: int | None = None
    current_team_name: str | None = None
    current_pick_expires_at: datetime | None = None
    seconds_remaining: int | None = None
    phase_seconds_remaining: int | None = None
    phase_type: Literal[
        "lobby_countdown",
        "prestart_countdown",
        "pick_clock",
        "pick_transition",
        "auto_picking",
    ] | None = None
    pick_state: Literal[
        "WAITING_FOR_PICK",
        "AUTO_PICKING",
        "PICK_SUBMITTED",
    ] = "WAITING_FOR_PICK"
    auto_pick_seconds_remaining: int | None = None
    current_pick_timer_seconds: int = 90
    timer_started_at: datetime | None = None
    timer_paused_at: datetime | None = None
    timer_paused_total_seconds: int = 0
    server_state_seq: int = 0
    user_team_id: int | None = None
    can_make_pick: bool
    created_at: datetime
    updated_at: datetime


class MockDraftRoomSnapshotRead(BaseModel):
    draft_room: MockDraftRoomRead
    events: list[DraftEventEnvelopeRead] = Field(default_factory=list)
    latest_seq: int = 0
