from datetime import datetime
import re
from typing import Optional
import base64
import binascii
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 12 characters and include one uppercase letter, "
    "one lowercase letter, one number, and one special character."
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
        or len(value) > 128
        or not any(character.isupper() for character in value)
        or not any(character.islower() for character in value)
        or not any(character.isdigit() for character in value)
        or not SPECIAL_CHARACTER_PATTERN.search(value)
    ):
        raise ValueError(PASSWORD_POLICY_MESSAGE)
    return value


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    email: str
    password: str
    username: Optional[str] = Field(default=None, max_length=80)
    beta_access_reservation: str | None = None

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

    @field_validator("beta_access_reservation")
    @classmethod
    def normalize_beta_access_reservation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


MAX_AVATAR_DATA_URL_BYTES = 250 * 1024
MAX_AVATAR_DATA_URL_LENGTH = 350 * 1024
JPEG_DATA_URL_PREFIX = "data:image/jpeg;base64,"


class UserProfileUpdate(BaseModel):
    """The limited, self-service profile fields supported during beta."""

    first_name: str | None = Field(default=None, max_length=50)
    avatar_url: str | None = Field(default=None, max_length=MAX_AVATAR_DATA_URL_LENGTH)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("manager name is required")
        return normalized

    @field_validator("avatar_url", mode="before")
    @classmethod
    def validate_avatar_url(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Enter a valid public HTTPS image address.")
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.startswith("data:"):
            if not normalized.startswith(JPEG_DATA_URL_PREFIX):
                raise ValueError("Profile photos must be JPEG images selected through the app.")
            encoded = normalized[len(JPEG_DATA_URL_PREFIX):]
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("Profile photo data is invalid.") from None
            if not decoded.startswith(b"\xff\xd8\xff"):
                raise ValueError("Profile photos must be valid JPEG images.")
            if len(decoded) > MAX_AVATAR_DATA_URL_BYTES:
                raise ValueError("Profile photos must be 250 KB or smaller.")
            return normalized
        if len(normalized) > 2048:
            raise ValueError("Profile image URL must be 2,048 characters or fewer.")
        parsed = urlparse(normalized)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Enter a valid public HTTPS image address.")
        return normalized

    @model_validator(mode="after")
    def require_profile_change(self) -> "UserProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one profile field is required")
        return self


class UserLogin(BaseModel):
    email: str
    password: str
    beta_access_reservation: str | None = None

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

    @field_validator("beta_access_reservation")
    @classmethod
    def normalize_beta_access_reservation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    email: str
    username: str | None = None
    avatar_url: str | None = None
    is_admin: bool = False
    created_at: datetime
    email_verified_at: datetime | None = None
    # A redeemed Early Access code is stored on the user and can be honored by
    # the alpha subscription system without storing the raw code.
    early_access_pro_eligible: bool = False


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


class AuthMessageResponse(BaseModel):
    success: bool = True
    message: str


class PasswordResetRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email_field(cls, value: str) -> str:
        return normalize_email(value)


class PasswordResetValidate(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class PasswordResetValidateResponse(BaseModel):
    valid: bool


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)


class PasswordResetCompleteResponse(BaseModel):
    status: str = "password_reset_complete"
    sessions_revoked: bool = True


class PasswordChangeFields(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("current_password", "new_password", "confirm_new_password")
    @classmethod
    def require_password_value(cls, value: str) -> str:
        if not value:
            raise ValueError("password is required")
        return value


class PasswordResetWithCurrentPassword(PasswordChangeFields):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email_field(cls, value: str) -> str:
        return normalize_email(value)


class AuthenticatedPasswordChange(PasswordChangeFields):
    pass


class SessionRead(BaseModel):
    id: int
    issued_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    is_current: bool = False


class SessionsResponse(BaseModel):
    sessions: list[SessionRead]
