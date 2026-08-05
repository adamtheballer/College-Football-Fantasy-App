from datetime import datetime
from pydantic import BaseModel


class PlayerTradeValueRead(BaseModel):
    week: int
    value: float
    raw_cfb27_rating: int | None = None
    current_value_rating: float | None = None
    tier: str
    positional_value_rank: int | None = None
    weekly_change: float | None = None
    confidence: float
    policy_version: str
    calculated_at: datetime | None = None
    factor_breakdown: dict | None = None
    explanations: list[dict] = []


class PlayerTradeValueHistoryRead(BaseModel):
    current: PlayerTradeValueRead | None = None
    history: list[PlayerTradeValueRead] = []
