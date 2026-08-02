from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class BetaAccessValidationRequest(BaseModel):
    email: str
    code: str

    @field_validator("email", "code")
    @classmethod
    def require_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value is required")
        return normalized


class BetaAccessValidationResponse(BaseModel):
    reservation_token: str
    reservation_expires_at: datetime
    email: str
    existing_account: bool = False
