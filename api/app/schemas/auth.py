from datetime import datetime
import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 12 characters and include one uppercase letter, "
    "one number, and one special character."
)
SPECIAL_CHARACTER_PATTERN = re.compile(r"[^A-Za-z0-9]")


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or "@" not in normalized:
        raise ValueError("valid email is required")
    return normalized


def validate_password_strength(value: str) -> str:
    if (
        len(value) < 12
        or not any(character.isupper() for character in value)
        or not any(character.isdigit() for character in value)
        or not SPECIAL_CHARACTER_PATTERN.search(value)
    ):
        raise ValueError(PASSWORD_POLICY_MESSAGE)
    return value


class UserCreate(BaseModel):
    first_name: str
    email: str
    password: str
    username: Optional[str] = None

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("first name is required")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email_field(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("username")
    @classmethod
    def normalize_username_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email_field(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, value: str) -> str:
        if not value:
            raise ValueError("password is required")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    email: str
    username: str | None = None
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    access_token_expires_at: datetime
    token_type: str = "bearer"
    user: UserRead


class RefreshResponse(BaseModel):
    access_token: str
    access_token_expires_at: datetime
    token_type: str = "bearer"


class LogoutResponse(BaseModel):
    success: bool
