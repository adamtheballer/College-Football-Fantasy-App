from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.notification import (
    LeagueNotificationPreference,
    LeagueNotificationPreferences,
    LeagueNotificationPreferencesUpdate,
    NotificationList,
    NotificationPreferences,
    NotificationRead,
    NotificationUnreadCount,
    PushTokenCreate,
    PushTokenRead,
)
from collegefootballfantasy_api.app.services.notification_service import (
    create_test_alert as create_test_alert_record,
    dismiss_notification as dismiss_notification_record,
    get_league_preferences as get_league_preferences_data,
    get_notification_preferences,
    get_unread_count as get_unread_count_data,
    list_user_alerts,
    mark_notification_read as mark_notification_read_record,
    register_push_token as register_push_token_record,
    update_league_preferences as update_league_preferences_data,
    update_notification_preferences,
)

router = APIRouter()


@router.post("/tokens", response_model=PushTokenRead)
def register_push_token(
    payload: PushTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PushTokenRead:
    return register_push_token_record(
        db=db,
        current_user_id=current_user.id,
        payload=payload,
    )


@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferences:
    return get_notification_preferences(db, current_user.id)


@router.post("/preferences", response_model=NotificationPreferences)
def update_preferences(
    payload: NotificationPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferences:
    return update_notification_preferences(
        db=db,
        current_user_id=current_user.id,
        payload=payload,
    )


@router.get("/alerts", response_model=NotificationList)
def list_alerts(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationList:
    return list_user_alerts(db=db, current_user_id=current_user.id, limit=limit)


@router.get("/unread-count", response_model=NotificationUnreadCount)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationUnreadCount:
    return get_unread_count_data(db=db, current_user_id=current_user.id)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    return mark_notification_read_record(db=db, notification_id=notification_id, current_user_id=current_user.id)


@router.post("/{notification_id}/dismiss", response_model=NotificationRead)
def dismiss_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    return dismiss_notification_record(db=db, notification_id=notification_id, current_user_id=current_user.id)


@router.post("/alerts/test", response_model=NotificationRead)
def create_test_alert(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    return create_test_alert_record(db=db, current_user_id=current_user.id)


@router.get("/league-preferences", response_model=LeagueNotificationPreferences)
def get_league_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueNotificationPreferences:
    return get_league_preferences_data(db=db, current_user_id=current_user.id)


@router.post("/league-preferences", response_model=LeagueNotificationPreferences)
def update_league_preferences(
    payload: LeagueNotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueNotificationPreferences:
    return update_league_preferences_data(
        db=db,
        current_user_id=current_user.id,
        payload=payload,
    )
