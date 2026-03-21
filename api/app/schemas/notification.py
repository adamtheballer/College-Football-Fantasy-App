from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PushTokenCreate(BaseModel):
    device_token: str
    platform: str = "unknown"


class PushTokenRead(PushTokenCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None = None
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
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None


class LeagueNotificationPreference(BaseModel):
    league_id: int
    league_name: str | None = None
    enabled: bool = True
    injury_alerts: bool = True
    big_play_alerts: bool = True
    projection_alerts: bool = True


class LeagueNotificationPreferences(BaseModel):
    data: list[LeagueNotificationPreference]


class LeagueNotificationPreferenceUpdate(BaseModel):
    league_id: int
    enabled: bool = True
    injury_alerts: bool = True
    big_play_alerts: bool = True
    projection_alerts: bool = True


class LeagueNotificationPreferencesUpdate(BaseModel):
    items: list[LeagueNotificationPreferenceUpdate]


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_type: str
    title: str
    body: str
    payload: dict | None = None
    sent_at: datetime


class NotificationList(BaseModel):
    data: list[NotificationRead]
    total: int
