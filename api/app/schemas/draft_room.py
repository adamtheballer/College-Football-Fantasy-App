from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class DraftRoomTeamRead(BaseModel):
    id: int
    name: str
    owner_user_id: int | None = None
    owner_name: str | None = None
    lobby_joined: bool = False
    lobby_connected: bool = False
    lobby_ready: bool = False


class DraftRoomPickRead(BaseModel):
    id: int
    overall_pick: int
    round_number: int
    round_pick: int
    team_id: int
    team_name: str
    player_id: int
    player_name: str
    player_position: str
    player_school: str
    made_by_user_id: int | None = None
    created_at: datetime


class DraftRosterPlayerRead(BaseModel):
    player_id: int
    player_name: str
    position: str
    school: str
    slot: str
    projected_fantasy_points: float | None = None


class DraftRosterTeamRead(BaseModel):
    team_id: int
    team_name: str
    total_projected_points: float
    position_counts: dict[str, int]
    slots: dict[str, list[DraftRosterPlayerRead]]


class DraftRoomRead(BaseModel):
    draft_room_id: int
    league_id: int
    draft_id: int
    status: str
    draft_status: Literal["waiting", "active", "paused", "complete"]
    pick_timer_seconds: int
    roster_slots: dict[str, int]
    draft_order: list[int] = Field(default_factory=list)
    drafted_player_ids: list[int] = Field(default_factory=list)
    available_player_count: int = 0
    rosters_by_team: list[DraftRosterTeamRead] = Field(default_factory=list)
    lobby_ready_count: int = 0
    lobby_joined_count: int = 0
    lobby_connected_count: int = 0
    teams: list[DraftRoomTeamRead]
    picks: list[DraftRoomPickRead]
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


class DraftQueueItemRead(BaseModel):
    id: int
    priority: int
    player_id: int
    player_name: str
    player_position: str
    player_school: str
    player_class: str | None = None
    projected_fantasy_points: float | None = None
    adp: float | None = None


class DraftQueueRead(BaseModel):
    draft_id: int
    league_id: int
    team_id: int
    count: int
    data: list[DraftQueueItemRead] = Field(default_factory=list)


class DraftPickCreate(BaseModel):
    player_id: int


class DraftRoomStatusUpdateRequest(BaseModel):
    status: Literal["active", "paused", "filling", "lobby_open", "countdown", "abandoned"]


class DraftSlotMoveRequest(BaseModel):
    from_slot: int = Field(ge=1, le=40)
    to_slot: int = Field(ge=1, le=40)


class DraftPracticeSetupRequest(BaseModel):
    team_count: int | None = Field(default=None, ge=2, le=40)
    reset_existing: bool = True
    start_now: bool = False
    mock_team_prefix: str = "Mock Team"


class DraftPlayerImportRow(BaseModel):
    external_id: str | None = None
    name: str
    position: str
    school: str
    image_url: str | None = None
    player_class: str | None = None
    adp: float | None = None
    projected_fantasy_points: float | None = None
    projection_stats: dict[str, float | int | None] | None = None


class DraftPlayerImportRequest(BaseModel):
    replace_mode: Literal["upsert", "replace_offense_pool"] = "upsert"
    rows: list[DraftPlayerImportRow]


class DraftPlayerImportResponse(BaseModel):
    received: int
    created: int
    updated: int
    removed: int


class DraftSheetSyncRequest(BaseModel):
    sheet_url: HttpUrl
    worksheet_gid: str | None = "0"
    worksheet_names: list[str] = Field(default_factory=list)
    replace_mode: Literal["upsert", "replace_offense_pool"] = "replace_offense_pool"
    watchlist_name: str = "CFB Master Board"


class DraftSheetSyncErrorRow(BaseModel):
    row_number: int
    reason: str
    raw: dict[str, str] | None = None


class DraftSheetSyncSampleRow(BaseModel):
    player: str
    fantasy_proj: float


class DraftSheetSyncResponse(BaseModel):
    received: int
    valid_rows: int
    imported: DraftPlayerImportResponse
    watchlist_id: int
    watchlist_name: str
    watchlist_player_count: int
    invalid_rows: list[DraftSheetSyncErrorRow] = Field(default_factory=list)
    sheet_id: str
    matched_players: int = 0
    unmatched_players: int = 0
    unmatched_player_names: list[str] = Field(default_factory=list)
    sample_imported_rows: list[DraftSheetSyncSampleRow] = Field(default_factory=list)


class DraftEventEnvelopeRead(BaseModel):
    event_id: str
    event: str
    event_type: str
    league_id: int
    entity_type: str
    entity_id: int | None = None
    seq: int
    schema_version: int = 1
    at: datetime
    payload: dict = Field(default_factory=dict)


class DraftRoomSnapshotRead(BaseModel):
    draft_room: DraftRoomRead
    events: list[DraftEventEnvelopeRead] = Field(default_factory=list)
    latest_seq: int = 0


class LeagueEventListRead(BaseModel):
    data: list[DraftEventEnvelopeRead] = Field(default_factory=list)
    latest_seq: int = 0


class DraftQueueAddRequest(BaseModel):
    player_id: int


class DraftQueueReorderRequest(BaseModel):
    player_ids: list[int] = Field(default_factory=list)


class DraftLobbyReadyRequest(BaseModel):
    ready: bool
