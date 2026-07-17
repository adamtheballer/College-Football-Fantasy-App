from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_plain_text_body(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("message body cannot be empty")
    if "<" in normalized or ">" in normalized:
        raise ValueError("messages must be plain text")
    if any(ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized):
        raise ValueError("message body contains unsupported control characters")
    return normalized


class ChatDirectThreadCreate(BaseModel):
    recipient_user_id: int = Field(gt=0)


class ChatMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    client_message_id: str | None = Field(default=None, max_length=100)
    reply_to_message_id: int | None = Field(default=None, gt=0)

    @field_validator("body")
    @classmethod
    def validate_plain_text_body(cls, value: str) -> str:
        return _validate_plain_text_body(value)

    @field_validator("client_message_id")
    @classmethod
    def normalize_client_message_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ChatMessageEdit(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def validate_plain_text_body(cls, value: str) -> str:
        return _validate_plain_text_body(value)


class ChatReadStateUpdate(BaseModel):
    last_read_message_id: int | None = Field(default=None, gt=0)


class ChatParticipantRead(BaseModel):
    user_id: int
    joined_at: datetime
    display_name: str
    fantasy_team_name: str | None


class ChatMessagePreview(BaseModel):
    id: int
    sender_display_name: str | None
    body: str | None
    message_type: str
    created_at: datetime


class ChatThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    thread_type: str
    title: str | None
    created_by_user_id: int | None
    direct_user_low_id: int | None
    direct_user_high_id: int | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    participants: list[ChatParticipantRead] = Field(default_factory=list)
    other_participant: ChatParticipantRead | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0


class ChatThreadList(BaseModel):
    data: list[ChatThreadRead]
    total: int


class ChatMessageRead(BaseModel):
    id: int
    thread_id: int
    league_id: int
    sender_user_id: int | None
    message_type: str
    body: str | None
    metadata: dict
    client_message_id: str | None
    reply_to_message_id: int | None
    edited_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    sender_display_name: str | None
    sender_fantasy_team_name: str | None
    reply_to_message: ChatMessagePreview | None = None


class ChatMessagePage(BaseModel):
    data: list[ChatMessageRead]
    next_before_message_id: int | None = None
    next_after_message_id: int | None = None


class ChatReadReceipt(BaseModel):
    thread_id: int
    league_id: int
    unread_count: int
    total_unread: int


class ChatUnreadLeagueRead(BaseModel):
    league_id: int
    unread: int


class ChatUnreadSummary(BaseModel):
    total_unread: int
    leagues: list[ChatUnreadLeagueRead]
