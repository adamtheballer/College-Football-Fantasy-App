from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.notification import (
    NotificationDeliveryAttempt,
    NotificationLeaguePreference,
    NotificationLog,
    NotificationPreference,
    PushToken,
)
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.team import Team
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

DEFAULT_DELIVERY_CHANNELS = ("push", "email")
TERMINAL_ATTEMPT_STATUSES = {"delivered", "failed", "canceled", "skipped"}
NOTIFICATION_DELIVERY_STATES = {"pending", "sent", "failed", "read", "dismissed"}
NOTIFICATION_TYPE_CATEGORIES = {
    "draft_on_clock": "draft",
    "draft_pick_made": "draft",
    "draft_1h": "draft",
    "draft_start": "draft",
    "trade_proposed": "trade",
    "trade_accepted": "trade",
    "trade_vetoed": "trade",
    "trade_processed": "trade",
    "waiver_processed": "waiver",
    "waiver_failed": "waiver",
    "lineup_lock_warning": "lineup",
    "player_injury": "injury",
    "score_close_game": "score",
    "stat_correction": "scoring",
    "league_invite": "league",
    "commissioner_action": "commissioner",
    "injury": "injury",
    "touchdown": "score",
    "big_play": "score",
    "usage": "usage",
    "waiver": "waiver",
    "projection": "projection",
    "trade": "trade",
    "trade_sent": "trade",
    "trade_accepted": "trade",
    "trade_rejected": "trade",
    "trade_proposed": "trade",
    "trade_cancelled": "trade",
    "trade_vetoed": "trade",
    "trade_processed": "trade",
}


def legacy_user_key(user_id: int) -> str:
    return str(user_id)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_notification_type(alert_type: str) -> str:
    return alert_type.strip().lower()


def notification_category(alert_type: str) -> str:
    normalized = normalize_notification_type(alert_type)
    return NOTIFICATION_TYPE_CATEGORIES.get(normalized, normalized.split("_", 1)[0] or "general")


def _serialize_log(row: NotificationLog) -> NotificationRead:
    return NotificationRead(
        id=row.id,
        alert_type=row.alert_type,
        title=row.title,
        body=row.body,
        payload=row.payload,
        league_id=row.league_id,
        delivery_state=row.delivery_state,
        source_entity_type=row.source_entity_type,
        source_entity_id=row.source_entity_id,
        deep_link=row.deep_link,
        sent_at=row.sent_at,
        read_at=row.read_at,
        dismissed_at=row.dismissed_at,
    )


def register_push_token(
    db: Session,
    current_user_id: int,
    payload: PushTokenCreate,
) -> PushTokenRead:
    existing = db.query(PushToken).filter(PushToken.device_token == payload.device_token).first()
    if existing:
        existing.user_id = current_user_id
        existing.user_key = legacy_user_key(current_user_id)
        existing.platform = payload.platform
        existing.enabled = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    token = PushToken(
        user_id=current_user_id,
        user_key=legacy_user_key(current_user_id),
        device_token=payload.device_token,
        platform=payload.platform,
        enabled=True,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def get_notification_preferences(db: Session, current_user_id: int) -> NotificationPreferences:
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user_id).first()
    if not prefs:
        return NotificationPreferences()
    return NotificationPreferences(
        push_enabled=prefs.push_enabled,
        email_enabled=prefs.email_enabled,
        in_app_enabled=prefs.in_app_enabled,
        draft_alerts=prefs.draft_alerts,
        injury_alerts=prefs.injury_alerts,
        touchdown_alerts=prefs.touchdown_alerts,
        usage_alerts=prefs.usage_alerts,
        waiver_alerts=prefs.waiver_alerts,
        projection_alerts=prefs.projection_alerts,
        lineup_reminders=prefs.lineup_reminders,
        category_toggles=prefs.category_toggles,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end,
    )


def update_notification_preferences(
    db: Session,
    current_user_id: int,
    payload: NotificationPreferences,
) -> NotificationPreferences:
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user_id).first()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user_id, user_key=legacy_user_key(current_user_id))
    else:
        prefs.user_id = current_user_id
        prefs.user_key = legacy_user_key(current_user_id)
    prefs.push_enabled = payload.push_enabled
    prefs.email_enabled = payload.email_enabled
    prefs.in_app_enabled = payload.in_app_enabled
    prefs.draft_alerts = payload.draft_alerts
    prefs.injury_alerts = payload.injury_alerts
    prefs.touchdown_alerts = payload.touchdown_alerts
    prefs.usage_alerts = payload.usage_alerts
    prefs.waiver_alerts = payload.waiver_alerts
    prefs.projection_alerts = payload.projection_alerts
    prefs.lineup_reminders = payload.lineup_reminders
    prefs.category_toggles = payload.category_toggles
    prefs.quiet_hours_start = payload.quiet_hours_start
    prefs.quiet_hours_end = payload.quiet_hours_end
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return get_notification_preferences(db, current_user_id)


def _log_matches_user(log: NotificationLog, user_id: int) -> bool:
    if log.user_id is not None:
        return log.user_id == user_id
    return log.user_key == legacy_user_key(user_id)


def _global_pref_allows(alert_type: str, prefs: NotificationPreference | None) -> bool:
    if not prefs:
        return True
    if not prefs.in_app_enabled:
        return False
    category = notification_category(alert_type)
    toggles = prefs.category_toggles or {}
    if category in toggles:
        return bool(toggles[category])
    if category == "injury":
        return prefs.injury_alerts
    if category == "score":
        return prefs.touchdown_alerts
    if category == "usage":
        return prefs.usage_alerts
    if category == "waiver":
        return prefs.waiver_alerts
    if category == "projection":
        return prefs.projection_alerts
    if category == "lineup":
        return prefs.lineup_reminders
    if category == "draft":
        return prefs.draft_alerts
    return True


def _league_pref_allows(alert_type: str, pref: NotificationLeaguePreference | None) -> bool:
    if not pref:
        return True
    if not pref.enabled:
        return False
    category = notification_category(alert_type)
    if category == "injury":
        return pref.injury_alerts
    if category == "score":
        return pref.big_play_alerts
    if category == "projection":
        return pref.projection_alerts
    return True


def _log_league_allowed(
    *,
    row: NotificationLog,
    current_user_id: int,
    rostered_player_ids: set[int],
    rostered_player_leagues: dict[int, set[int]],
    league_pref_by_id: dict[int, NotificationLeaguePreference],
) -> bool:
    payload = row.payload or {}
    payload_league_id = row.league_id or payload.get("league_id")
    if isinstance(payload_league_id, int):
        return _league_pref_allows(row.alert_type, league_pref_by_id.get(payload_league_id))

    if row.user_id == current_user_id or row.user_key == legacy_user_key(current_user_id):
        return True

    player_id = payload.get("player_id")
    if not isinstance(player_id, int) or player_id not in rostered_player_ids:
        return False
    return any(
        _league_pref_allows(row.alert_type, league_pref_by_id.get(league_id))
        for league_id in rostered_player_leagues.get(player_id, set())
    )


def _is_visible_log(
    *,
    row: NotificationLog,
    current_user_id: int,
    global_prefs: NotificationPreference | None,
    rostered_player_ids: set[int],
    rostered_player_leagues: dict[int, set[int]],
    league_pref_by_id: dict[int, NotificationLeaguePreference],
) -> bool:
    if row.dismissed_at is not None or row.delivery_state == "dismissed":
        return False
    if not _log_matches_user(row, current_user_id):
        payload = row.payload or {}
        player_id = payload.get("player_id")
        if not isinstance(player_id, int) or player_id not in rostered_player_ids:
            return False
    if not _global_pref_allows(row.alert_type, global_prefs):
        return False
    return _log_league_allowed(
        row=row,
        current_user_id=current_user_id,
        rostered_player_ids=rostered_player_ids,
        rostered_player_leagues=rostered_player_leagues,
        league_pref_by_id=league_pref_by_id,
    )


def list_user_alerts(db: Session, current_user_id: int, limit: int = 50) -> NotificationList:
    global_prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user_id).first()
    rostered_player_rows = (
        db.query(RosterEntry.player_id, Team.league_id)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.owner_user_id == current_user_id)
        .distinct()
        .all()
    )
    rostered_player_leagues: dict[int, set[int]] = {}
    for player_id, league_id in rostered_player_rows:
        if player_id is None or league_id is None:
            continue
        rostered_player_leagues.setdefault(player_id, set()).add(league_id)
    rostered_player_ids = set(rostered_player_leagues.keys())

    league_pref_by_id = {
        pref.league_id: pref
        for pref in db.query(NotificationLeaguePreference)
        .filter(NotificationLeaguePreference.user_id == current_user_id)
        .all()
    }

    rows = db.query(NotificationLog).order_by(NotificationLog.sent_at.desc()).limit(limit * 8).all()
    data: list[NotificationRead] = []
    for row in rows:
        if not _is_visible_log(
            row=row,
            current_user_id=current_user_id,
            global_prefs=global_prefs,
            rostered_player_ids=rostered_player_ids,
            rostered_player_leagues=rostered_player_leagues,
            league_pref_by_id=league_pref_by_id,
        ):
            continue
        data.append(_serialize_log(row))
        if len(data) >= limit:
            break
    return NotificationList(data=data, total=len(data))


def get_unread_count(db: Session, current_user_id: int) -> NotificationUnreadCount:
    visible = list_user_alerts(db, current_user_id=current_user_id, limit=500)
    unread = sum(1 for row in visible.data if row.read_at is None and row.delivery_state not in {"read", "dismissed"})
    return NotificationUnreadCount(unread_count=unread)


def _get_user_notification(db: Session, *, notification_id: int, current_user_id: int) -> NotificationLog:
    row = db.get(NotificationLog, notification_id)
    if not row or not _log_matches_user(row, current_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification not found")
    return row


def mark_notification_read(db: Session, *, notification_id: int, current_user_id: int) -> NotificationRead:
    row = _get_user_notification(db, notification_id=notification_id, current_user_id=current_user_id)
    now = _utc_now()
    row.read_at = row.read_at or now
    if row.delivery_state != "dismissed":
        row.delivery_state = "read"
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_log(row)


def dismiss_notification(db: Session, *, notification_id: int, current_user_id: int) -> NotificationRead:
    row = _get_user_notification(db, notification_id=notification_id, current_user_id=current_user_id)
    now = _utc_now()
    row.read_at = row.read_at or now
    row.dismissed_at = row.dismissed_at or now
    row.delivery_state = "dismissed"
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_log(row)


def create_notification_event(
    db: Session,
    *,
    user_id: int,
    alert_type: str,
    title: str,
    body: str,
    league_id: int | None = None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
    source_entity_type: str | None = None,
    source_entity_id: int | None = None,
    deep_link: str | None = None,
    delivery_state: str = "sent",
) -> NotificationLog | None:
    if delivery_state not in NOTIFICATION_DELIVERY_STATES:
        raise ValueError(f"unsupported notification delivery state: {delivery_state}")
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    if not _global_pref_allows(alert_type, prefs):
        return None

    if dedupe_key:
        existing = (
            db.query(NotificationLog)
            .filter(NotificationLog.user_id == user_id, NotificationLog.dedupe_key == dedupe_key)
            .first()
        )
        if existing:
            return existing

    row = NotificationLog(
        user_id=user_id,
        user_key=legacy_user_key(user_id),
        league_id=league_id,
        alert_type=alert_type,
        title=title,
        body=body,
        payload=payload,
        delivery_state=delivery_state,
        dedupe_key=dedupe_key,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        deep_link=deep_link,
        sent_at=_utc_now(),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if dedupe_key:
            return (
                db.query(NotificationLog)
                .filter(NotificationLog.user_id == user_id, NotificationLog.dedupe_key == dedupe_key)
                .first()
            )
        raise
    return row


def create_test_alert(db: Session, current_user_id: int) -> NotificationRead:
    roster_row = (
        db.query(RosterEntry.player_id, Team.league_id)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.owner_user_id == current_user_id)
        .first()
    )
    payload: dict[str, int | str] = {"source": "test"}
    if roster_row and roster_row[0] and roster_row[1]:
        payload["player_id"] = int(roster_row[0])
        payload["league_id"] = int(roster_row[1])
    alert = NotificationLog(
        user_id=current_user_id,
        user_key=legacy_user_key(current_user_id),
        league_id=int(payload["league_id"]) if isinstance(payload.get("league_id"), int) else None,
        alert_type="PROJECTION",
        title="Projection Change",
        body="Test projection alert created.",
        payload=payload,
        delivery_state="sent",
        source_entity_type="test",
        deep_link="/alerts",
        sent_at=datetime.utcnow(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _serialize_log(alert)


def get_league_preferences(db: Session, current_user_id: int) -> LeagueNotificationPreferences:
    memberships = (
        db.query(LeagueMember, League)
        .join(League, League.id == LeagueMember.league_id)
        .filter(LeagueMember.user_id == current_user_id)
        .all()
    )
    pref_by_league = {
        pref.league_id: pref
        for pref in db.query(NotificationLeaguePreference)
        .filter(NotificationLeaguePreference.user_id == current_user_id)
        .all()
    }
    data: list[LeagueNotificationPreference] = []
    for membership, league in memberships:
        pref = pref_by_league.get(league.id)
        data.append(
            LeagueNotificationPreference(
                league_id=league.id,
                league_name=league.name,
                enabled=pref.enabled if pref else True,
                injury_alerts=pref.injury_alerts if pref else True,
                big_play_alerts=pref.big_play_alerts if pref else True,
                projection_alerts=pref.projection_alerts if pref else True,
            )
        )
    return LeagueNotificationPreferences(data=data)


def update_league_preferences(
    db: Session,
    current_user_id: int,
    payload: LeagueNotificationPreferencesUpdate,
) -> LeagueNotificationPreferences:
    allowed_league_ids = {
        row[0]
        for row in db.query(LeagueMember.league_id)
        .filter(LeagueMember.user_id == current_user_id)
        .all()
    }
    for item in payload.items:
        if item.league_id not in allowed_league_ids:
            continue
        pref = (
            db.query(NotificationLeaguePreference)
            .filter(
                NotificationLeaguePreference.user_id == current_user_id,
                NotificationLeaguePreference.league_id == item.league_id,
            )
            .first()
        )
        if not pref:
            pref = NotificationLeaguePreference(
                user_id=current_user_id,
                user_key=legacy_user_key(current_user_id),
                league_id=item.league_id,
            )
        else:
            pref.user_id = current_user_id
            pref.user_key = legacy_user_key(current_user_id)
        pref.enabled = item.enabled
        pref.injury_alerts = item.injury_alerts
        pref.big_play_alerts = item.big_play_alerts
        pref.projection_alerts = item.projection_alerts
        db.add(pref)
    db.commit()
    return get_league_preferences(db, current_user_id)


def queue_scheduled_notification(
    db: Session,
    *,
    league_id: int,
    user_id: int,
    notification_type: str,
    scheduled_for: datetime,
    channels: tuple[str, ...] = DEFAULT_DELIVERY_CHANNELS,
) -> ScheduledNotification:
    scheduled = ScheduledNotification(
        league_id=league_id,
        user_id=user_id,
        notification_type=notification_type,
        scheduled_for=scheduled_for,
    )
    db.add(scheduled)
    db.flush()
    for channel in channels:
        db.add(
            NotificationDeliveryAttempt(
                scheduled_notification_id=scheduled.id,
                user_id=user_id,
                channel=channel,
                attempt_number=1,
                status="pending",
            )
        )
    return scheduled


def schedule_draft_notifications(db: Session, league_id: int, user_id: int, draft_time: datetime) -> None:
    draft_time = draft_time.astimezone(timezone.utc)
    queue_scheduled_notification(
        db,
        league_id=league_id,
        user_id=user_id,
        notification_type="draft_1h",
        scheduled_for=draft_time - timedelta(hours=1),
    )
    queue_scheduled_notification(
        db,
        league_id=league_id,
        user_id=user_id,
        notification_type="draft_start",
        scheduled_for=draft_time,
    )


def cancel_scheduled_notifications(db: Session, league_id: int, *, reason: str = "canceled") -> None:
    now = datetime.utcnow()
    scheduled_rows = (
        db.query(ScheduledNotification)
        .filter(
            ScheduledNotification.league_id == league_id,
            ScheduledNotification.canceled_at.is_(None),
            ScheduledNotification.sent_at.is_(None),
        )
        .all()
    )
    if not scheduled_rows:
        return

    scheduled_ids = [row.id for row in scheduled_rows]
    for row in scheduled_rows:
        row.canceled_at = now
        db.add(row)

    attempts = (
        db.query(NotificationDeliveryAttempt)
        .filter(
            NotificationDeliveryAttempt.scheduled_notification_id.in_(scheduled_ids),
            NotificationDeliveryAttempt.status == "pending",
        )
        .all()
    )
    for attempt in attempts:
        attempt.status = "canceled"
        attempt.attempted_at = now
        attempt.error_message = reason
        db.add(attempt)


def record_delivery_attempt(
    db: Session,
    *,
    scheduled_notification_id: int,
    channel: str,
    status: str,
    error_message: str | None = None,
    delivered_at: datetime | None = None,
) -> NotificationDeliveryAttempt:
    latest = (
        db.query(NotificationDeliveryAttempt)
        .filter(
            NotificationDeliveryAttempt.scheduled_notification_id == scheduled_notification_id,
            NotificationDeliveryAttempt.channel == channel,
        )
        .order_by(NotificationDeliveryAttempt.attempt_number.desc())
        .first()
    )

    now = datetime.utcnow()
    if latest is None or latest.status in TERMINAL_ATTEMPT_STATUSES:
        latest_attempt_number = latest.attempt_number if latest else 0
        latest = NotificationDeliveryAttempt(
            scheduled_notification_id=scheduled_notification_id,
            user_id=(
                db.query(ScheduledNotification.user_id)
                .filter(ScheduledNotification.id == scheduled_notification_id)
                .scalar()
            ),
            channel=channel,
            attempt_number=latest_attempt_number + 1,
        )

    latest.status = status
    latest.attempted_at = now
    latest.error_message = error_message
    latest.delivered_at = delivered_at if status == "delivered" else None
    db.add(latest)
    db.flush()
    refresh_scheduled_notification_state(db, scheduled_notification_id)
    return latest


def refresh_scheduled_notification_state(db: Session, scheduled_notification_id: int) -> None:
    scheduled = db.query(ScheduledNotification).filter(ScheduledNotification.id == scheduled_notification_id).first()
    if not scheduled:
        return
    attempts = (
        db.query(NotificationDeliveryAttempt)
        .filter(NotificationDeliveryAttempt.scheduled_notification_id == scheduled_notification_id)
        .all()
    )
    if not attempts or any(attempt.status == "pending" for attempt in attempts):
        return
    delivered_times = [
        attempt.delivered_at or attempt.attempted_at for attempt in attempts if attempt.status == "delivered"
    ]
    if delivered_times:
        scheduled.sent_at = max(ts for ts in delivered_times if ts is not None)
    db.add(scheduled)
