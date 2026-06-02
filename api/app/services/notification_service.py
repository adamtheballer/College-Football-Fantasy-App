import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.notification import (
    NotificationDeliveryAttempt,
    NotificationLeaguePreference,
    NotificationLog,
    NotificationPreference,
    PushToken,
)
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
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
    PushTokenCreate,
    PushTokenRead,
)

DEFAULT_DELIVERY_CHANNELS = ("push", "email")
TERMINAL_ATTEMPT_STATUSES = {"delivered", "failed", "canceled", "skipped"}
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

try:
    from pywebpush import webpush as webpush_send
except Exception:  # pragma: no cover - optional dependency for browser push delivery
    webpush_send = None


def legacy_user_key(user_id: int) -> str:
    return str(user_id)


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
        draft_alerts=prefs.draft_alerts,
        injury_alerts=prefs.injury_alerts,
        touchdown_alerts=prefs.touchdown_alerts,
        usage_alerts=prefs.usage_alerts,
        waiver_alerts=prefs.waiver_alerts,
        projection_alerts=prefs.projection_alerts,
        lineup_reminders=prefs.lineup_reminders,
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
    prefs.draft_alerts = payload.draft_alerts
    prefs.injury_alerts = payload.injury_alerts
    prefs.touchdown_alerts = payload.touchdown_alerts
    prefs.usage_alerts = payload.usage_alerts
    prefs.waiver_alerts = payload.waiver_alerts
    prefs.projection_alerts = payload.projection_alerts
    prefs.lineup_reminders = payload.lineup_reminders
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
    if alert_type == "INJURY":
        return prefs.injury_alerts
    if alert_type in {"TOUCHDOWN", "BIG_PLAY"}:
        return prefs.touchdown_alerts
    if alert_type == "USAGE":
        return prefs.usage_alerts
    if alert_type == "WAIVER":
        return prefs.waiver_alerts
    if alert_type == "PROJECTION":
        return prefs.projection_alerts
    if alert_type.startswith("draft_"):
        return prefs.draft_alerts
    return True


def _league_pref_allows(alert_type: str, pref: NotificationLeaguePreference | None) -> bool:
    if not pref:
        return True
    if not pref.enabled:
        return False
    if alert_type == "INJURY":
        return pref.injury_alerts
    if alert_type in {"TOUCHDOWN", "BIG_PLAY"}:
        return pref.big_play_alerts
    if alert_type == "PROJECTION":
        return pref.projection_alerts
    return True


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
        if not _log_matches_user(row, current_user_id):
            continue
        if not _global_pref_allows(row.alert_type, global_prefs):
            continue
        payload = row.payload or {}
        player_id = payload.get("player_id")
        if not isinstance(player_id, int) or player_id not in rostered_player_ids:
            continue
        payload_league_id = payload.get("league_id")
        candidate_league_ids = (
            {payload_league_id}
            if isinstance(payload_league_id, int)
            else rostered_player_leagues.get(player_id, set())
        )
        if not candidate_league_ids:
            continue
        if not any(
            _league_pref_allows(row.alert_type, league_pref_by_id.get(league_id))
            for league_id in candidate_league_ids
        ):
            continue
        data.append(
            NotificationRead(
                id=row.id,
                alert_type=row.alert_type,
                title=row.title,
                body=row.body,
                payload=row.payload,
                sent_at=row.sent_at,
            )
        )
        if len(data) >= limit:
            break
    return NotificationList(data=data, total=len(data))


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
        alert_type="PROJECTION",
        title="Projection Change",
        body="Test projection alert created.",
        payload=payload,
        sent_at=datetime.utcnow(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return NotificationRead(
        id=alert.id,
        alert_type=alert.alert_type,
        title=alert.title,
        body=alert.body,
        payload=alert.payload,
        sent_at=alert.sent_at,
    )


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


def _touchdown_count_from_stats(stats: dict | None) -> int:
    if not isinstance(stats, dict):
        return 0
    total = 0
    for key in ("PassingTouchdowns", "RushingTouchdowns", "ReceivingTouchdowns"):
        try:
            total += int(float(stats.get(key) or 0))
        except (TypeError, ValueError):
            continue
    return max(0, total)


def _send_push_notifications(tokens: list[str], *, title: str, body: str, payload: dict | None = None) -> int:
    def _send_web_push(subscription_token: str) -> bool:
        if webpush_send is None:
            return False
        if not settings.web_push_vapid_private_key:
            return False
        normalized = (subscription_token or "").strip()
        if not normalized.startswith("{"):
            return False
        try:
            subscription = json.loads(normalized)
        except json.JSONDecodeError:
            return False
        if not isinstance(subscription, dict) or not subscription.get("endpoint"):
            return False
        claims_subject = settings.web_push_vapid_subject or "mailto:support@cfbfantasy.app"
        try:
            webpush_send(
                subscription_info=subscription,
                data=json.dumps({"title": title, "body": body, "data": payload or {}}),
                vapid_private_key=settings.web_push_vapid_private_key,
                vapid_claims={"sub": claims_subject},
            )
            return True
        except Exception:
            return False

    sent = 0
    for token in tokens:
        normalized = (token or "").strip()
        if normalized.startswith("ExponentPushToken["):
            try:
                httpx.post(
                    EXPO_PUSH_URL,
                    json={"to": normalized, "title": title, "body": body, "data": payload or {}},
                    timeout=8.0,
                )
                sent += 1
            except Exception:
                continue
            continue
        if _send_web_push(normalized):
            sent += 1
    return sent


def emit_live_player_alerts(
    db: Session,
    *,
    season: int,
    week: int,
    max_logs_scan: int = 5000,
) -> dict[str, int]:
    roster_rows = (
        db.query(RosterEntry, Team, Player)
        .join(Team, Team.id == RosterEntry.team_id)
        .join(Player, Player.id == RosterEntry.player_id)
        .filter(Team.owner_user_id.isnot(None))
        .all()
    )
    if not roster_rows:
        return {"created": 0, "push_sent": 0, "injury_alerts": 0, "big_play_alerts": 0}

    player_ids = {int(player.id) for _entry, _team, player in roster_rows}
    user_ids = {int(team.owner_user_id) for _entry, team, _player in roster_rows if team.owner_user_id is not None}

    stat_rows = (
        db.query(PlayerStat)
        .filter(
            PlayerStat.player_id.in_(player_ids),
            PlayerStat.season == season,
            PlayerStat.week == week,
        )
        .all()
    )
    stat_by_player = {int(row.player_id): row for row in stat_rows}

    injury_rows = (
        db.query(Injury)
        .filter(
            Injury.player_id.in_(player_ids),
            Injury.season == season,
            Injury.week == week,
        )
        .order_by(Injury.updated_at.desc(), Injury.id.desc())
        .all()
    )
    injury_by_player: dict[int, Injury] = {}
    for injury in injury_rows:
        injury_by_player.setdefault(int(injury.player_id), injury)

    pref_by_user = {
        int(pref.user_id): pref
        for pref in db.query(NotificationPreference)
        .filter(NotificationPreference.user_id.in_(user_ids))
        .all()
        if pref.user_id is not None
    }
    league_pref_by_user_league = {
        (int(pref.user_id), int(pref.league_id)): pref
        for pref in db.query(NotificationLeaguePreference)
        .filter(NotificationLeaguePreference.user_id.in_(user_ids))
        .all()
        if pref.user_id is not None
    }
    push_tokens_by_user: dict[int, list[str]] = {}
    for token in (
        db.query(PushToken)
        .filter(PushToken.user_id.in_(user_ids), PushToken.enabled.is_(True))
        .all()
    ):
        if token.user_id is None:
            continue
        push_tokens_by_user.setdefault(int(token.user_id), []).append(token.device_token)

    recent_logs = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.user_id.in_(user_ids),
            NotificationLog.alert_type.in_(("INJURY", "TOUCHDOWN", "BIG_PLAY")),
        )
        .order_by(NotificationLog.sent_at.desc())
        .limit(max(100, max_logs_scan))
        .all()
    )
    existing_alert_keys = {
        str((row.payload or {}).get("alert_key"))
        for row in recent_logs
        if isinstance(row.payload, dict) and (row.payload or {}).get("alert_key")
    }

    created = 0
    push_sent = 0
    injury_alerts = 0
    big_play_alerts = 0

    for _entry, team, player in roster_rows:
        if team.owner_user_id is None:
            continue
        user_id = int(team.owner_user_id)
        global_pref = pref_by_user.get(user_id)
        league_pref = league_pref_by_user_league.get((user_id, int(team.league_id)))

        injury = injury_by_player.get(int(player.id))
        injury_status = (injury.status or "").strip().upper() if injury else ""
        injury_active = injury_status and injury_status not in {"FULL", "ACTIVE", "HEALTHY", "PROBABLE"}
        if injury_active and _global_pref_allows("INJURY", global_pref) and _league_pref_allows("INJURY", league_pref):
            alert_key = f"injury:{user_id}:{team.league_id}:{player.id}:{injury_status}"
            if alert_key not in existing_alert_keys:
                title = f"⚠️ {player.name} injury update"
                detail = injury.injury or "Status changed"
                body = f"{player.name} is now {injury_status}. {detail}"
                payload = {
                    "alert_key": alert_key,
                    "league_id": int(team.league_id),
                    "team_id": int(team.id),
                    "player_id": int(player.id),
                    "status": injury_status,
                    "season": season,
                    "week": week,
                }
                db.add(
                    NotificationLog(
                        user_id=user_id,
                        user_key=legacy_user_key(user_id),
                        alert_type="INJURY",
                        title=title,
                        body=body,
                        payload=payload,
                        sent_at=datetime.utcnow(),
                    )
                )
                existing_alert_keys.add(alert_key)
                created += 1
                injury_alerts += 1
                if not global_pref or global_pref.push_enabled:
                    push_sent += _send_push_notifications(
                        push_tokens_by_user.get(user_id, []),
                        title=title,
                        body=body,
                        payload=payload,
                    )

        stat_row = stat_by_player.get(int(player.id))
        touchdown_total = _touchdown_count_from_stats(stat_row.stats if stat_row else None)
        if touchdown_total > 0 and _global_pref_allows("TOUCHDOWN", global_pref) and _league_pref_allows("TOUCHDOWN", league_pref):
            alert_key = f"td:{user_id}:{team.league_id}:{player.id}:{touchdown_total}"
            if alert_key not in existing_alert_keys:
                title = f"🏈 Big play: {player.name}"
                body = f"{player.name} now has {touchdown_total} TDs this week. Check your matchup swing."
                payload = {
                    "alert_key": alert_key,
                    "league_id": int(team.league_id),
                    "team_id": int(team.id),
                    "player_id": int(player.id),
                    "touchdown_total": touchdown_total,
                    "season": season,
                    "week": week,
                }
                db.add(
                    NotificationLog(
                        user_id=user_id,
                        user_key=legacy_user_key(user_id),
                        alert_type="TOUCHDOWN",
                        title=title,
                        body=body,
                        payload=payload,
                        sent_at=datetime.utcnow(),
                    )
                )
                existing_alert_keys.add(alert_key)
                created += 1
                big_play_alerts += 1
                if not global_pref or global_pref.push_enabled:
                    push_sent += _send_push_notifications(
                        push_tokens_by_user.get(user_id, []),
                        title=title,
                        body=body,
                        payload=payload,
                    )

    db.flush()
    return {
        "created": created,
        "push_sent": push_sent,
        "injury_alerts": injury_alerts,
        "big_play_alerts": big_play_alerts,
    }
