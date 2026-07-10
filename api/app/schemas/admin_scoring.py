from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScoringCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: int = Field(gt=0, strict=True)
    stats: dict[str, Any]
    reason: str | None = Field(default=None, max_length=500)


class FinalizeWeekRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: int = Field(gt=0, strict=True)


class ProviderRowMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: int = Field(gt=0, strict=True)
    match_confidence: int = Field(default=100, ge=0, le=100, strict=True)
