from datetime import datetime, time

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class PushTokenCreate(BaseModel):
    # ``device_token`` remains an accepted input alias for existing native
    # clients. The API calls it a subscription because OneSignal—not Expo—is
    # the canonical provider.
    subscription_id: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("subscription_id", "device_token"),
    )
    platform: str = Field(default="web", min_length=1, max_length=30)
    provider: Literal["onesignal"] = "onesignal"


class PushTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None = None
    provider: str
    platform: str
    enabled: bool = True


class NotificationPreferences(BaseModel):
    push_enabled: bool = True
    email_enabled: bool = True
    draft_alerts: bool = True
    injury_alerts: bool = True
    touchdown_alerts: bool = False
    usage_alerts: bool = True
    waiver_alerts: bool = True
    projection_alerts: bool = True
    lineup_reminders: bool = True
    trade_alerts: bool = True
    chat_alerts: bool = True
    matchup_results: bool = True
    matchup_start_alerts: bool = True
    matchup_result_alerts: bool = True
    big_play_alerts: bool = False
    long_rush_alerts: bool = False
    long_reception_alerts: bool = False
    long_pass_alerts: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=64)

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_quiet_hour(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("quiet hours must use HH:MM time") from exc
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class LeagueNotificationPreference(BaseModel):
    league_id: int
    league_name: str | None = None
    enabled: bool = True
    injury_alerts: bool = True
    big_play_alerts: bool = True
    projection_alerts: bool = True
    draft_alerts: bool = True
    trade_alerts: bool = True
    waiver_alerts: bool = True
    matchup_start_alerts: bool = True
    matchup_result_alerts: bool = True
    lineup_reminders: bool = True
    touchdown_alerts: bool = False
    long_rush_alerts: bool = False
    long_reception_alerts: bool = False
    long_pass_alerts: bool = False


class LeagueNotificationPreferences(BaseModel):
    data: list[LeagueNotificationPreference]


class LeagueNotificationPreferenceUpdate(BaseModel):
    league_id: int
    enabled: bool = True
    injury_alerts: bool = True
    big_play_alerts: bool = True
    projection_alerts: bool = True
    draft_alerts: bool = True
    trade_alerts: bool = True
    waiver_alerts: bool = True
    matchup_start_alerts: bool = True
    matchup_result_alerts: bool = True
    lineup_reminders: bool = True
    touchdown_alerts: bool = False
    long_rush_alerts: bool = False
    long_reception_alerts: bool = False
    long_pass_alerts: bool = False


class LeagueNotificationPreferencesUpdate(BaseModel):
    items: list[LeagueNotificationPreferenceUpdate]


class NotificationDestination(BaseModel):
    type: Literal["draft", "trade", "waivers", "matchup", "chat", "league"]
    league_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_type: str
    title: str
    body: str
    payload: dict | None = None
    sent_at: datetime
    read_at: datetime | None = None
    category: str = "SYSTEM"
    event_type: str | None = None
    scope: Literal[
        "direct_user",
        "league_member",
        "matchup_participant",
        "private_trade_participant",
        "system",
    ] = "direct_user"
    destination: NotificationDestination | None = None


class NotificationList(BaseModel):
    data: list[NotificationRead]
    total: int
    unread_count: int = 0


class NotificationMarkRead(BaseModel):
    read: bool = True


class NotificationMarkAllRead(BaseModel):
    updated: int


class NotificationSubscriptionDetach(BaseModel):
    disabled: int
