from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.notification import (
    LeagueNotificationPreference,
    LeagueNotificationPreferences,
    LeagueNotificationPreferencesUpdate,
    NotificationList,
    NotificationMarkAllRead,
    NotificationMarkRead,
    NotificationPreferences,
    NotificationRead,
    NotificationSubscriptionDetach,
    PushTokenCreate,
    PushTokenRead,
)
from collegefootballfantasy_api.app.services.notification_service import (
    create_test_alert as create_test_alert_record,
    detach_push_subscriptions,
    disable_push_subscription,
    get_league_preferences as get_league_preferences_data,
    get_notification_preferences,
    list_user_alerts,
    mark_all_notifications_read,
    mark_notification_read,
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
    try:
        return register_push_token_record(
            db=db,
            current_user_id=current_user.id,
            payload=payload,
        )
    except PermissionError as exc:
        # Do not let a caller enumerate whether another account owns an
        # opaque OneSignal subscription ID.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification subscription not found") from exc


@router.post("/tokens/detach", response_model=NotificationSubscriptionDetach)
def detach_push_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationSubscriptionDetach:
    """Detach all active local subscriptions before the browser logs out of OneSignal."""
    return NotificationSubscriptionDetach(disabled=detach_push_subscriptions(db, current_user_id=current_user.id))


@router.delete("/tokens/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def disable_push_token(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    disable_push_subscription(db, current_user_id=current_user.id, subscription_id=subscription_id)


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


@router.patch("/alerts/{notification_id}", response_model=NotificationRead)
def mark_alert_read(
    notification_id: int,
    payload: NotificationMarkRead,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    alert = mark_notification_read(
        db,
        current_user_id=current_user.id,
        notification_id=notification_id,
        read=payload.read,
    )
    if alert is None:
        # A missing or foreign notification is intentionally indistinguishable.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification not found")
    return alert


@router.post("/alerts/read-all", response_model=NotificationMarkAllRead)
def mark_all_alerts_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationMarkAllRead:
    return NotificationMarkAllRead(updated=mark_all_notifications_read(db, current_user_id=current_user.id))


@router.post("/alerts/test", response_model=NotificationRead)
def create_test_alert(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    if current_user.is_admin is False and settings.is_production:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification test endpoint not found")
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
