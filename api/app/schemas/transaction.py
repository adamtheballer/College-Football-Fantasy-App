from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    team_id: int
    transaction_type: str
    player_id: int | None = None
    related_player_id: int | None = None
    created_by_user_id: int | None = None
    reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TransactionList(BaseModel):
    data: list[TransactionRead]
    total: int
    limit: int
    offset: int
