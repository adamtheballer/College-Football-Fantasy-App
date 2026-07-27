from datetime import datetime

from pydantic import BaseModel, Field


class LeaguePlayerHistoryTeam(BaseModel):
    id: int | None = None
    name: str | None = None


class LeaguePlayerHistoryManager(BaseModel):
    id: int | None = None
    name: str | None = None


class LeaguePlayerCurrentStatus(BaseModel):
    status: str
    fantasy_team_id: int | None = None
    fantasy_team_name: str | None = None
    manager_name: str | None = None


class LeaguePlayerHistoryEvent(BaseModel):
    id: int
    event_type: str
    occurred_at: datetime
    fantasy_team: LeaguePlayerHistoryTeam | None = None
    from_team: LeaguePlayerHistoryTeam | None = None
    to_team: LeaguePlayerHistoryTeam | None = None
    manager: LeaguePlayerHistoryManager | None = None
    draft_id: int | None = None
    draft_pick_id: int | None = None
    trade_id: int | None = None
    waiver_claim_id: int | None = None
    transaction_id: int | None = None
    player_value_at_event: float | None = None
    player_name: str
    position: str
    school: str
    metadata: dict | None = None


class LeaguePlayerHistoryRead(BaseModel):
    league_id: int
    player_id: int
    current_status: LeaguePlayerCurrentStatus
    events: list[LeaguePlayerHistoryEvent]
    total: int
    limit: int
    offset: int
