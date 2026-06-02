from datetime import datetime

from pydantic import BaseModel, Field


class AdminActionRead(BaseModel):
    id: int
    league_id: int
    actor_user_id: int | None = None
    action_type: str
    target_type: str
    target_id: int | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class AdminActionListRead(BaseModel):
    data: list[AdminActionRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
