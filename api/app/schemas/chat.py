from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


CHAT_MESSAGE_TYPES = {"user", "system", "trade", "waiver", "draft", "scoring", "commissioner"}


class LeagueMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    message_type: str = "user"
    parent_message_id: int | None = None

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message body is required")
        return cleaned

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in CHAT_MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        return normalized


class LeagueMessageUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message body is required")
        return cleaned


class LeagueMessageReportCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class LeagueChatReadUpdate(BaseModel):
    last_read_message_id: int | None = None


class LeagueMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    user_id: int
    body: str
    message_type: str
    parent_message_id: int | None = None
    deleted_at: datetime | None = None
    edited_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    can_edit: bool = False
    can_delete: bool = False


class LeagueMessageList(BaseModel):
    data: list[LeagueMessageRead]
    total: int
    limit: int
    before_id: int | None = None
    after_id: int | None = None
    unread_count: int


class LeagueChatReadState(BaseModel):
    league_id: int
    last_read_message_id: int | None = None
    last_read_at: datetime | None = None
    unread_count: int


class LeagueMessageReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    reporter_user_id: int
    reason: str
    status: str
    created_at: datetime
