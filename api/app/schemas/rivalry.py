from datetime import datetime

from pydantic import BaseModel, Field


class RivalryInviteCreate(BaseModel):
    recipient_team_id: int = Field(gt=0)


class RivalryCandidateRead(BaseModel):
    team_id: int
    team_name: str
    manager_user_id: int
    manager_name: str
    manager_avatar_url: str | None = None


class RivalryInviteRead(BaseModel):
    id: int
    league_id: int
    sender_team_id: int
    sender_team_name: str
    sender_manager_name: str
    sender_manager_avatar_url: str | None = None
    recipient_team_id: int
    recipient_team_name: str
    recipient_manager_name: str
    recipient_manager_avatar_url: str | None = None
    status: str
    expires_at: datetime
    created_at: datetime


class RivalryRead(BaseModel):
    id: int
    league_id: int
    opponent_team_id: int
    opponent_team_name: str
    opponent_manager_name: str
    opponent_manager_avatar_url: str | None = None
    accepted_at: datetime
    status: str


class RivalrySeriesRead(BaseModel):
    wins: int = 0
    losses: int = 0
    ties: int = 0
    last_meeting: str | None = None


class RivalryMatchupRead(BaseModel):
    is_rivalry_matchup: bool = False
    rivalry_id: int | None = None
    opponent_team_id: int | None = None
    opponent_team_name: str | None = None
    series: RivalrySeriesRead | None = None


class LeagueRivalryViewRead(BaseModel):
    eligible: bool
    rivalry: RivalryRead | None = None
    outgoing_invite: RivalryInviteRead | None = None
    incoming_invites: list[RivalryInviteRead] = []
    candidates: list[RivalryCandidateRead] = []
