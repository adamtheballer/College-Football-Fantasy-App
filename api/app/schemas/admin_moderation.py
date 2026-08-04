from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModerationEventRead(BaseModel):
    """Admin-safe moderation audit record; blocked content is never returned."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None = None
    league_id: int | None = None
    field_name: str
    reason_code: str
    created_at: datetime


class ModerationEventList(BaseModel):
    data: list[ModerationEventRead]
    total: int
    limit: int
    offset: int
