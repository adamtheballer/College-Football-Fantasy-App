from datetime import datetime

from pydantic import BaseModel


class DraftRoomTeamRead(BaseModel):
    id: int
    name: str
    owner_user_id: int | None = None
    owner_name: str | None = None


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


class DraftRoomRead(BaseModel):
    league_id: int
    draft_id: int
    status: str
    pick_timer_seconds: int
    roster_slots: dict[str, int]
    teams: list[DraftRoomTeamRead]
    picks: list[DraftRoomPickRead]
    current_pick: int
    current_round: int
    current_round_pick: int
    current_team_id: int | None = None
    current_team_name: str | None = None
    user_team_id: int | None = None
    can_make_pick: bool


class DraftPickCreate(BaseModel):
    player_id: int
