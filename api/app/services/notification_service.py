"""Canonical durable notification orchestration.

Domain services enqueue one idempotent event in their own transaction. A
dedicated worker owns in-app creation and external delivery after commit, so a
provider outage cannot roll back a trade, waiver, draft, or chat operation.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
from typing import Literal
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.notification import (
    NotificationDeliveryAttempt,
    NotificationLeaguePreference,
    NotificationLog,
    NotificationPreference,
    PushToken,
)
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.notification import (
    LeagueNotificationPreference,
    LeagueNotificationPreferences,
    LeagueNotificationPreferencesUpdate,
    NotificationDestination,
    NotificationList,
    NotificationPreferences,
    NotificationRead,
    PushTokenCreate,
    PushTokenRead,
)
from collegefootballfantasy_api.app.services.notification_providers import (
    EmailNotificationProvider,
    PushNotificationProvider,
    get_email_provider,
    get_push_provider,
)
from collegefootballfantasy_api.app.services.notification_events import (
    NotificationScope,
    canonical_event_type,
    destination_for_event,
    get_notification_event,
    render_event_content,
)


DELIVERY_CHANNELS = ("in_app", "push", "email")
TERMINAL_ATTEMPT_STATUSES = {"delivered", "provider_accepted", "failed", "canceled", "skipped", "retry"}
DELIVERY_RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), timedelta(hours=1))
URGENT_PUSH_CATEGORIES = {"DRAFT", "TRADE", "WAIVER"}
NOTIFICATION_SCOPES = {scope.value for scope in NotificationScope}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def legacy_user_key(user_id: int) -> str:
    return str(user_id)


def external_user_identity(user_id: int) -> str:
    """Stable provider identity; never use an email or mutable display name."""
    return f"cfb_user:{user_id}"


def _event_key(channel: str, event_key: str) -> str:
    return f"{event_key}:{channel}"


def _provider_idempotency_key(channel: str, event_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, _event_key(channel, event_key)))


def _event_metadata(event_type: str, payload: dict, league_name: str) -> tuple[str, str, str]:
    return render_event_content(event_type, payload, league_name)


def _destination_for(event_type: str, *, league_id: int | None, payload: dict) -> dict | None:
    return destination_for_event(event_type, league_id=league_id, payload=payload)


def _validated_destination(payload: dict | None) -> NotificationDestination | None:
    if not payload or not isinstance(payload.get("destination"), dict):
        return None
    try:
        return NotificationDestination.model_validate(payload["destination"])
    except ValueError:
        return None


def _serialize_log(row: NotificationLog) -> NotificationRead:
    return NotificationRead(
        id=row.id,
        alert_type=row.alert_type,
        title=row.title,
        body=row.body,
        payload=row.payload,
        sent_at=row.sent_at,
        read_at=row.read_at,
        category=row.category,
        event_type=row.alert_type,
        scope=row.scope if row.scope in NOTIFICATION_SCOPES else "direct_user",
        destination=_validated_destination(row.payload),
    )


def _notification_log_user_filter(user_id: int):
    return or_(
        NotificationLog.user_id == user_id,
        and_(NotificationLog.user_id.is_(None), NotificationLog.user_key == legacy_user_key(user_id)),
    )


def register_push_token(db: Session, current_user_id: int, payload: PushTokenCreate) -> PushTokenRead:
    """Race-safe upsert of a provider subscription without returning its ID."""
    active = (
        db.query(PushToken)
        .filter(PushToken.device_token == payload.subscription_id, PushToken.enabled.is_(True))
        .one_or_none()
    )
    if active is not None and active.user_id not in {None, current_user_id}:
        # A browser subscription is an account-bound capability. Do not let a
        # second authenticated account take it over, even if it somehow knows
        # the opaque provider subscription ID.
        raise PermissionError("notification subscription does not belong to this user")
    existing = active
    if existing is None:
        # Re-enable a retained row only for its prior owner.  A different
        # user gets a new active row after the previous owner explicitly
        # detached, preserving the ownership audit trail.
        existing = (
            db.query(PushToken)
            .filter(
                PushToken.device_token == payload.subscription_id,
                PushToken.user_id == current_user_id,
                PushToken.enabled.is_(False),
            )
            .order_by(PushToken.updated_at.desc(), PushToken.id.desc())
            .first()
        )
    if existing is None:
        try:
            with db.begin_nested():
                existing = PushToken(
                    user_id=current_user_id,
                    user_key=legacy_user_key(current_user_id),
                    device_token=payload.subscription_id,
                    platform=payload.platform,
                    provider=payload.provider,
                    external_user_id=external_user_identity(current_user_id),
                    enabled=True,
                )
                db.add(existing)
                db.flush()
        except IntegrityError:
            existing = (
                db.query(PushToken)
                .filter(PushToken.device_token == payload.subscription_id, PushToken.enabled.is_(True))
                .one()
            )
            if existing.user_id not in {None, current_user_id}:
                raise PermissionError("notification subscription does not belong to this user")
    existing.user_id = current_user_id
    existing.user_key = legacy_user_key(current_user_id)
    existing.platform = payload.platform
    existing.provider = payload.provider
    existing.external_user_id = external_user_identity(current_user_id)
    existing.enabled = True
    db.add(existing)
    db.commit()
    db.refresh(existing)
    return PushTokenRead(
        id=existing.id,
        user_id=existing.user_id,
        provider=existing.provider,
        platform=existing.platform,
        enabled=existing.enabled,
    )


def disable_push_subscription(db: Session, *, current_user_id: int, subscription_id: int) -> None:
    subscription = (
        db.query(PushToken)
        .filter(PushToken.id == subscription_id, PushToken.user_id == current_user_id)
        .one_or_none()
    )
    if subscription is None:
        return
    subscription.enabled = False
    db.add(subscription)
    db.commit()


def detach_push_subscriptions(db: Session, *, current_user_id: int) -> int:
    """Disable this account's active browser subscriptions before OneSignal logout.

    This intentionally leaves the rows and their previous owner intact.  A
    later account can claim the subscription only after this explicit detach.
    """
    disabled = (
        db.query(PushToken)
        .filter(PushToken.user_id == current_user_id, PushToken.enabled.is_(True))
        .update({PushToken.enabled: False}, synchronize_session=False)
    )
    db.commit()
    return int(disabled)


def get_notification_preferences(db: Session, current_user_id: int) -> NotificationPreferences:
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user_id).first()
    if not prefs:
        return NotificationPreferences()
    return NotificationPreferences(
        push_enabled=prefs.push_enabled,
        email_enabled=prefs.email_enabled,
        draft_alerts=prefs.draft_alerts,
        injury_alerts=prefs.injury_alerts,
        # Retain this legacy API property for already-installed clients, but
        # never reactivate a standalone touchdown alert.
        touchdown_alerts=False,
        usage_alerts=prefs.usage_alerts,
        waiver_alerts=prefs.waiver_alerts,
        projection_alerts=prefs.projection_alerts,
        lineup_reminders=prefs.lineup_reminders,
        trade_alerts=prefs.trade_alerts,
        chat_alerts=prefs.chat_alerts,
        matchup_results=prefs.matchup_results,
        matchup_start_alerts=prefs.matchup_start_alerts,
        matchup_result_alerts=prefs.matchup_result_alerts,
        big_play_alerts=prefs.big_play_alerts,
        long_rush_alerts=prefs.long_rush_alerts,
        long_reception_alerts=prefs.long_reception_alerts,
        long_pass_alerts=prefs.long_pass_alerts,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end,
        timezone=prefs.timezone,
    )


def update_notification_preferences(
    db: Session, current_user_id: int, payload: NotificationPreferences
) -> NotificationPreferences:
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user_id).first()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user_id, user_key=legacy_user_key(current_user_id))
    # Big Plays is the master switch.  Turning it off also clears every
    # long-play child control, so a later re-enable always requires an
    # explicit choice of the desired sub-alerts. Touchdowns are no longer a
    # product notification type; retain the storage field only for clients
    # built before this release.
    payload.touchdown_alerts = False
    if not payload.big_play_alerts:
        payload.long_rush_alerts = False
        payload.long_reception_alerts = False
        payload.long_pass_alerts = False
    for field in NotificationPreferences.model_fields:
        setattr(prefs, field, getattr(payload, field))
    prefs.user_id = current_user_id
    prefs.user_key = legacy_user_key(current_user_id)
    db.add(prefs)
    db.commit()
    return get_notification_preferences(db, current_user_id)


def list_user_alerts(db: Session, current_user_id: int, limit: int = 50) -> NotificationList:
    """Direct user events are visible without requiring a rostered player.

    Authorization is by the immutable recipient user ID (or a legacy user-key
    fallback), never by arbitrary data contained in the JSON payload.
    """
    bounded_limit = max(1, min(limit, 100))
    user_filter = _notification_log_user_filter(current_user_id)
    rows = (
        db.query(NotificationLog)
        .filter(user_filter)
        .order_by(NotificationLog.sent_at.desc(), NotificationLog.id.desc())
        .limit(bounded_limit)
        .all()
    )
    unread_count = db.query(func.count(NotificationLog.id)).filter(user_filter, NotificationLog.read_at.is_(None)).scalar() or 0
    return NotificationList(data=[_serialize_log(row) for row in rows], total=len(rows), unread_count=int(unread_count))


def mark_notification_read(db: Session, *, current_user_id: int, notification_id: int, read: bool = True) -> NotificationRead | None:
    row = (
        db.query(NotificationLog)
        .filter(NotificationLog.id == notification_id, _notification_log_user_filter(current_user_id))
        .one_or_none()
    )
    if row is None:
        return None
    row.read_at = utcnow() if read else None
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_log(row)


def mark_all_notifications_read(db: Session, *, current_user_id: int) -> int:
    updated = (
        db.query(NotificationLog)
        .filter(_notification_log_user_filter(current_user_id), NotificationLog.read_at.is_(None))
        .update({NotificationLog.read_at: utcnow()}, synchronize_session=False)
    )
    db.commit()
    return int(updated)


def get_league_preferences(db: Session, current_user_id: int) -> LeagueNotificationPreferences:
    memberships = (
        db.query(LeagueMember, League)
        .join(League, League.id == LeagueMember.league_id)
        .filter(LeagueMember.user_id == current_user_id)
        .all()
    )
    pref_by_league = {
        pref.league_id: pref
        for pref in db.query(NotificationLeaguePreference).filter(NotificationLeaguePreference.user_id == current_user_id).all()
    }
    return LeagueNotificationPreferences(
        data=[
            LeagueNotificationPreference(
                league_id=league.id,
                league_name=league.name,
                enabled=pref.enabled if (pref := pref_by_league.get(league.id)) else True,
                injury_alerts=pref.injury_alerts if pref else True,
                big_play_alerts=pref.big_play_alerts if pref else True,
                projection_alerts=pref.projection_alerts if pref else True,
                draft_alerts=pref.draft_alerts if pref else True,
                trade_alerts=pref.trade_alerts if pref else True,
                waiver_alerts=pref.waiver_alerts if pref else True,
                matchup_start_alerts=pref.matchup_start_alerts if pref else True,
                matchup_result_alerts=pref.matchup_result_alerts if pref else True,
                lineup_reminders=pref.lineup_reminders if pref else True,
                touchdown_alerts=False,
                long_rush_alerts=pref.long_rush_alerts if pref else False,
                long_reception_alerts=pref.long_reception_alerts if pref else False,
                long_pass_alerts=pref.long_pass_alerts if pref else False,
            )
            for _membership, league in memberships
        ]
    )


def update_league_preferences(
    db: Session, current_user_id: int, payload: LeagueNotificationPreferencesUpdate
) -> LeagueNotificationPreferences:
    allowed_league_ids = {
        league_id
        for (league_id,) in db.query(LeagueMember.league_id).filter(LeagueMember.user_id == current_user_id).all()
    }
    for item in payload.items:
        if item.league_id not in allowed_league_ids:
            continue
        pref = (
            db.query(NotificationLeaguePreference)
            .filter(NotificationLeaguePreference.user_id == current_user_id, NotificationLeaguePreference.league_id == item.league_id)
            .one_or_none()
        )
        if pref is None:
            pref = NotificationLeaguePreference(
                user_id=current_user_id, user_key=legacy_user_key(current_user_id), league_id=item.league_id
            )
        item.touchdown_alerts = False
        if not item.big_play_alerts:
            item.long_rush_alerts = False
            item.long_reception_alerts = False
            item.long_pass_alerts = False
        pref.enabled = item.enabled
        pref.injury_alerts = item.injury_alerts
        pref.big_play_alerts = item.big_play_alerts
        pref.projection_alerts = item.projection_alerts
        pref.draft_alerts = item.draft_alerts
        pref.trade_alerts = item.trade_alerts
        pref.waiver_alerts = item.waiver_alerts
        pref.matchup_start_alerts = item.matchup_start_alerts
        pref.matchup_result_alerts = item.matchup_result_alerts
        pref.lineup_reminders = item.lineup_reminders
        pref.touchdown_alerts = False
        pref.long_rush_alerts = item.long_rush_alerts
        pref.long_reception_alerts = item.long_reception_alerts
        pref.long_pass_alerts = item.long_pass_alerts
        db.add(pref)
    db.commit()
    return get_league_preferences(db, current_user_id)


def queue_notification_event(
    db: Session,
    *,
    league_id: int,
    user_id: int,
    event_type: str,
    event_key: str,
    scheduled_for: datetime | None = None,
    payload: dict | None = None,
    title: str | None = None,
    body: str | None = None,
    channels: tuple[str, ...] = DELIVERY_CHANNELS,
    scope: str | None = None,
) -> ScheduledNotification:
    """Create the durable per-recipient event exactly once in the caller transaction."""
    normalized_event_type = canonical_event_type(event_type)
    definition = get_notification_event(normalized_event_type)
    scope = scope or definition.privacy_scope.value
    if scope not in NOTIFICATION_SCOPES:
        raise ValueError("unsupported notification scope")
    existing = db.query(ScheduledNotification).filter(ScheduledNotification.event_key == event_key).one_or_none()
    if existing is not None:
        # A kickoff may be removed and later restored before delivery.  It is
        # safe to reopen a canceled, never-sent event with fresh attempts;
        # retain the canceled attempts as immutable history.
        if existing.status == "canceled" and existing.sent_at is None and normalized_event_type == "MATCHUP_START":
            existing.status = "pending"
            existing.canceled_at = None
            existing.completed_at = None
            existing.claimed_at = None
            existing.claim_heartbeat_at = None
            existing.claimed_by = None
            existing.scheduled_for = _as_utc(scheduled_for or utcnow())
            db.add(existing)
            for channel in channels:
                latest = (
                    db.query(NotificationDeliveryAttempt)
                    .filter(
                        NotificationDeliveryAttempt.scheduled_notification_id == existing.id,
                        NotificationDeliveryAttempt.channel == channel,
                    )
                    .order_by(NotificationDeliveryAttempt.attempt_number.desc())
                    .first()
                )
                db.add(
                    NotificationDeliveryAttempt(
                        scheduled_notification_id=existing.id,
                        user_id=existing.user_id,
                        channel=channel,
                        attempt_number=(latest.attempt_number if latest else 0) + 1,
                        status="pending",
                    )
                )
        return existing
    league = db.get(League, league_id)
    if league is None:
        raise ValueError("notification league does not exist")
    payload_data = dict(payload or {})
    payload_data["league_id"] = league_id
    destination = _destination_for(normalized_event_type, league_id=league_id, payload=payload_data)
    if destination is not None:
        payload_data["destination"] = destination
    payload_data["scope"] = scope
    category, default_title, default_body = _event_metadata(normalized_event_type, payload_data, league.name)
    try:
        with db.begin_nested():
            scheduled = ScheduledNotification(
                league_id=league_id,
                user_id=user_id,
                # Preserve established stored event names (for example
                # ``draft_start``) while templates/categories normalize them.
                notification_type=event_type,
                event_type=normalized_event_type,
                event_key=event_key,
                scope=scope,
                scheduled_for=_as_utc(scheduled_for or utcnow()),
                title=title or default_title,
                body=body or default_body,
                payload=payload_data,
                category=category,
                status="pending",
            )
            db.add(scheduled)
            db.flush()
            for channel in channels:
                if channel not in DELIVERY_CHANNELS:
                    raise ValueError(f"unsupported notification channel: {channel}")
                db.add(
                    NotificationDeliveryAttempt(
                        scheduled_notification_id=scheduled.id,
                        user_id=user_id,
                        channel=channel,
                        attempt_number=1,
                        status="pending",
                    )
                )
    except IntegrityError:
        scheduled = db.query(ScheduledNotification).filter(ScheduledNotification.event_key == event_key).one_or_none()
        if scheduled is None:
            raise
    return scheduled


def queue_scheduled_notification(
    db: Session,
    *,
    league_id: int,
    user_id: int,
    notification_type: str,
    scheduled_for: datetime,
    channels: tuple[str, ...] = DELIVERY_CHANNELS,
) -> ScheduledNotification:
    rounded = _as_utc(scheduled_for).replace(microsecond=0).isoformat()
    return queue_notification_event(
        db,
        league_id=league_id,
        user_id=user_id,
        event_type=notification_type,
        event_key=f"{notification_type.lower()}:{league_id}:{user_id}:{rounded}",
        scheduled_for=scheduled_for,
        channels=channels,
    )


def _localized_draft_time(draft_time: datetime, timezone_name: str) -> str:
    try:
        return _as_utc(draft_time).astimezone(ZoneInfo(timezone_name)).strftime("%b %-d at %-I:%M %p %Z")
    except (ValueError, ZoneInfoNotFoundError):
        return _as_utc(draft_time).isoformat()


def schedule_draft_notifications(db: Session, league_id: int, user_id: int, draft_time: datetime) -> None:
    """Schedule only a pre-draft reminder for an official scheduled draft.

    ``DRAFT_START`` is deliberately not scheduled here: it is emitted only
    after the draft state machine has actually entered ``on_clock``.
    """
    draft_time = _as_utc(draft_time)
    draft = db.query(Draft).filter(Draft.league_id == league_id).first()
    user = db.get(User, user_id)
    membership = (
        db.query(LeagueMember.id)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
        .first()
    )
    if draft is None or user is None or not user.is_active or membership is None:
        return
    if (draft.status or "scheduled").lower() != "scheduled":
        return
    now = utcnow()
    if draft_time <= now:
        return
    schedule_revision = draft.draft_version
    localized_time = _localized_draft_time(draft_time, draft.timezone or "UTC")
    if draft_time - now >= timedelta(hours=1):
        event_type = "DRAFT_1H"
        scheduled_for = draft_time - timedelta(hours=1)
        event_key = f"draft_1h:{draft.id}:{schedule_revision}:{user_id}"
    else:
        # A draft scheduled late cannot truthfully send a one-hour reminder.
        # Queue the documented fallback immediately, under server time.
        event_type = "DRAFT_SOON"
        scheduled_for = now
        event_key = f"draft_soon:{draft.id}:{schedule_revision}:{user_id}"
    queue_notification_event(
        db,
        league_id=league_id,
        user_id=user_id,
        event_type=event_type,
        event_key=event_key,
        scheduled_for=scheduled_for,
        payload={
            "draft_id": draft.id,
            "schedule_revision": schedule_revision,
            "localized_draft_time": localized_time,
        },
    )


def _matchup_start_revision(snapshots: list[LineupWeekSnapshot]) -> str:
    """Deterministic revision over only eligible starters and their kickoffs."""
    material = "|".join(
        f"{snapshot.player_id}:{snapshot.slot}:{_as_utc(snapshot.game_start_at).isoformat()}"
        for snapshot in sorted(snapshots, key=lambda item: (item.player_id, item.slot))
        if snapshot.game_start_at is not None
    )
    return sha256(material.encode("utf-8")).hexdigest()[:16]


def rebuild_matchup_start_notifications(db: Session, *, league_id: int, season: int, week: int) -> int:
    """Reconcile one kickoff event per eligible team owner/matchup/week revision.

    ``LineupWeekSnapshot`` is the authoritative frozen lineup input. Rows
    without a verified kickoff are intentionally ignored, so TBD/postponed or
    cancelled games (which have no usable kickoff) never create a reminder.
    """
    matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week == week)
        .all()
    )
    team_by_id = {
        team.id: team
        for team in db.query(Team).filter(Team.league_id == league_id).all()
    }
    owner_by_id = {
        user.id: user
        for user in db.query(User).filter(User.id.in_([team.owner_user_id for team in team_by_id.values() if team.owner_user_id])).all()
    }
    snapshots_by_team: dict[int, list[LineupWeekSnapshot]] = {}
    for snapshot in (
        db.query(LineupWeekSnapshot)
        .join(
            RosterEntry,
            and_(
                RosterEntry.league_id == LineupWeekSnapshot.league_id,
                RosterEntry.team_id == LineupWeekSnapshot.team_id,
                RosterEntry.player_id == LineupWeekSnapshot.player_id,
            ),
        )
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
            LineupWeekSnapshot.is_starter.is_(True),
            LineupWeekSnapshot.game_start_at.isnot(None),
            func.lower(RosterEntry.status) == "active",
            func.upper(LineupWeekSnapshot.slot).notin_(("BENCH", "IR")),
        )
        .all()
    ):
        snapshots_by_team.setdefault(snapshot.team_id, []).append(snapshot)

    desired_keys: set[str] = set()
    rescheduled = 0
    for matchup in matchups:
        for team_id in (matchup.home_team_id, matchup.away_team_id):
            team = team_by_id.get(team_id)
            starters = snapshots_by_team.get(team_id, [])
            owner = owner_by_id.get(team.owner_user_id) if team and team.owner_user_id else None
            if team is None or owner is None or not owner.is_active or not starters:
                continue
            kickoff = min(_as_utc(item.game_start_at) for item in starters if item.game_start_at is not None)
            revision = _matchup_start_revision(starters)
            # Keep one stable event per matchup recipient.  Before delivery
            # the event can be rescheduled as lineups or verified kickoffs
            # change; after delivery this key prevents any second alert.
            event_key = f"matchup_start:{matchup.id}:{owner.id}"
            desired_keys.add(event_key)
            opponent_id = matchup.away_team_id if team_id == matchup.home_team_id else matchup.home_team_id
            opponent = team_by_id.get(opponent_id)
            payload = {
                "matchup_id": matchup.id,
                "team_id": team_id,
                "season": season,
                "week": week,
                "opponent_team_name": opponent.name if opponent else "your opponent",
                "kickoff_revision": revision,
            }
            existing = db.query(ScheduledNotification).filter(ScheduledNotification.event_key == event_key).one_or_none()
            if existing is not None:
                if existing.sent_at is not None or existing.status == "delivered":
                    continue
                if existing.status == "claimed":
                    # A due event is already owned by the worker.  Do not
                    # race a lease by rewriting it during a lineup refresh.
                    continue
                if existing.status == "canceled":
                    existing = queue_notification_event(
                        db,
                        league_id=league_id,
                        user_id=owner.id,
                        event_type="MATCHUP_START",
                        event_key=event_key,
                        scheduled_for=kickoff,
                        payload=payload,
                    )
                schedule_changed = _as_utc(existing.scheduled_for) != kickoff
                revision_changed = (existing.payload or {}).get("kickoff_revision") != revision
                existing.scheduled_for = kickoff
                existing.payload = {
                    **payload,
                    "league_id": league_id,
                    "scope": NotificationScope.MATCHUP_PARTICIPANT.value,
                    "destination": _destination_for("MATCHUP_START", league_id=league_id, payload=payload),
                }
                existing.category, existing.title, existing.body = _event_metadata("MATCHUP_START", existing.payload, db.get(League, league_id).name)
                db.add(existing)
                rescheduled += int(schedule_changed or revision_changed)
                continue
            queue_notification_event(
                db,
                league_id=league_id,
                user_id=owner.id,
                event_type="MATCHUP_START",
                event_key=event_key,
                scheduled_for=kickoff,
                payload=payload,
            )

    obsolete = (
        db.query(ScheduledNotification)
        .filter(
            ScheduledNotification.league_id == league_id,
            or_(
                ScheduledNotification.event_key.like("matchup_start:%"),
                ScheduledNotification.event_key.like("matchup-start:%"),
            ),
            ScheduledNotification.status.in_(("pending", "retry", "claimed")),
            ScheduledNotification.canceled_at.is_(None),
        )
        .all()
    )
    now = utcnow()
    for event in obsolete:
        if event.event_key in desired_keys:
            continue
        event.status = "canceled"
        event.canceled_at = now
        event.completed_at = now
        event.claim_heartbeat_at = None
        db.add(event)
        (
            db.query(NotificationDeliveryAttempt)
            .filter(
                NotificationDeliveryAttempt.scheduled_notification_id == event.id,
                NotificationDeliveryAttempt.status == "pending",
            )
            .update(
                {
                    NotificationDeliveryAttempt.status: "canceled",
                    NotificationDeliveryAttempt.attempted_at: now,
                    NotificationDeliveryAttempt.error_message: "kickoff or lineup changed",
                },
                synchronize_session=False,
            )
        )
    return rescheduled


def rebuild_matchup_start_notifications_for_schedule(
    db: Session,
    *,
    season: int,
    weeks: set[int],
) -> int:
    """Refresh affected lineup snapshots after a verified kickoff update."""
    if not weeks:
        return 0
    # Delayed import avoids a module cycle: scoring invokes the single-league
    # notification reconciliation after it has refreshed snapshots.
    from collegefootballfantasy_api.app.services.scoring_service import create_or_refresh_lineup_snapshots

    queued = 0
    for league in db.query(League).filter(League.season_year == season).all():
        for week in sorted(weeks):
            create_or_refresh_lineup_snapshots(db, league.id, season, week)
            queued += rebuild_matchup_start_notifications(db, league_id=league.id, season=season, week=week)
    return queued


def _certified_matchup_revision(matchup: Matchup) -> str:
    material = ":".join(
        (
            str(matchup.id),
            (matchup.status or "").lower(),
            f"{float(matchup.home_score or 0.0):.2f}",
            f"{float(matchup.away_score or 0.0):.2f}",
        )
    )
    return sha256(material.encode("utf-8")).hexdigest()[:16]


def _matchup_outcome(own_score: float, opponent_score: float) -> str:
    if own_score > opponent_score:
        return "won"
    if own_score < opponent_score:
        return "lost"
    return "tied"


def _latest_certified_outcome(db: Session, *, matchup_id: int, user_id: int) -> str | None:
    rows = (
        db.query(ScheduledNotification)
        .filter(
            ScheduledNotification.user_id == user_id,
            ScheduledNotification.event_type.in_(("MATCHUP_FINAL", "MATCHUP_CORRECTED")),
        )
        .order_by(ScheduledNotification.id.desc())
        .all()
    )
    for row in rows:
        payload = row.payload or {}
        if payload.get("matchup_id") == matchup_id and payload.get("outcome") in {"won", "lost", "tied"}:
            return str(payload["outcome"])
    return None


def _format_matchup_score(value: float) -> str:
    return f"{value:g}"


def queue_certified_matchup_final_notifications(db: Session, matchup: Matchup) -> int:
    """Queue final notifications only for scoring-certified matchup statuses."""
    certified_status = (matchup.status or "").lower()
    if certified_status not in {"final", "stat_corrected"}:
        return 0
    revision = _certified_matchup_revision(matchup)
    teams = {
        team.id: team
        for team in db.query(Team).filter(Team.id.in_((matchup.home_team_id, matchup.away_team_id))).all()
    }
    owners = {
        user.id: user
        for user in db.query(User).filter(User.id.in_([team.owner_user_id for team in teams.values() if team.owner_user_id])).all()
    }
    queued = 0
    for team_id in (matchup.home_team_id, matchup.away_team_id):
        team = teams.get(team_id)
        owner = owners.get(team.owner_user_id) if team and team.owner_user_id else None
        if team is None or owner is None or not owner.is_active:
            continue
        opponent_id = matchup.away_team_id if team_id == matchup.home_team_id else matchup.home_team_id
        opponent = teams.get(opponent_id)
        own_score = float(matchup.home_score or 0.0) if team_id == matchup.home_team_id else float(matchup.away_score or 0.0)
        opponent_score = float(matchup.away_score or 0.0) if team_id == matchup.home_team_id else float(matchup.home_score or 0.0)
        outcome = _matchup_outcome(own_score, opponent_score)
        prior_outcome = _latest_certified_outcome(db, matchup_id=matchup.id, user_id=owner.id)
        correction = certified_status == "stat_corrected"
        event_type = "MATCHUP_CORRECTED" if correction else "MATCHUP_FINAL"
        event_key = (
            f"matchup_corrected:{matchup.id}:{owner.id}:{revision}"
            if correction
            else f"matchup_final:{matchup.id}:{owner.id}:{revision}"
        )
        before = db.query(ScheduledNotification.id).filter(ScheduledNotification.event_key == event_key).first()
        queue_notification_event(
            db,
            league_id=matchup.league_id,
            user_id=owner.id,
            event_type=event_type,
            event_key=event_key,
            channels=("in_app", "push", "email") if not correction or prior_outcome != outcome else ("in_app",),
            payload={
                "matchup_id": matchup.id,
                "team_id": team_id,
                "season": matchup.season,
                "week": matchup.week,
                "final_revision": revision,
                "correction_revision": revision if correction else None,
                "outcome": outcome,
                "opponent_team": opponent.name if opponent else None,
                "user_score": own_score,
                "opponent_score": opponent_score,
                "home_score": float(matchup.home_score or 0.0),
                "away_score": float(matchup.away_score or 0.0),
            },
        )
        queued += int(before is None)
    return queued


def intake_typed_big_play_notification(
    db: Session,
    *,
    league_id: int,
    user_id: int,
    event_type: Literal["LONG_RUSH", "LONG_RECEPTION", "LONG_PASS"],
    event_key: str,
    player_id: int,
    play_yards: int | None = None,
) -> ScheduledNotification | None:
    """Typed intake only; live data polling/inference remains intentionally absent."""
    if not settings.live_player_notifications_enabled:
        return None
    definition = get_notification_event(event_type)
    if definition.minimum_yards is None or play_yards is None or play_yards < definition.minimum_yards:
        return None
    return queue_notification_event(
        db,
        league_id=league_id,
        user_id=user_id,
        event_type=event_type,
        event_key=event_key,
        payload={"player_id": player_id},
        scope=NotificationScope.LEAGUE_MEMBER.value,
    )


def cancel_scheduled_notifications(
    db: Session,
    league_id: int,
    *,
    reason: str = "canceled",
    event_types: tuple[str, ...] | None = None,
) -> None:
    """Cancel only the requested pending outbox events.

    Draft rescheduling must not accidentally cancel trade, waiver, or matchup
    notifications queued in the same league.
    """
    now = utcnow()
    query = db.query(ScheduledNotification).filter(
        ScheduledNotification.league_id == league_id,
        ScheduledNotification.status.in_(("pending", "retry", "claimed")),
        ScheduledNotification.canceled_at.is_(None),
    )
    if event_types:
        normalized = tuple(event_type.upper() for event_type in event_types)
        query = query.filter(func.upper(func.coalesce(ScheduledNotification.event_type, ScheduledNotification.notification_type)).in_(normalized))
    rows = query.all()
    for row in rows:
        row.status = "canceled"
        row.canceled_at = now
        row.completed_at = now
        db.add(row)
        for attempt in db.query(NotificationDeliveryAttempt).filter(
            NotificationDeliveryAttempt.scheduled_notification_id == row.id,
            NotificationDeliveryAttempt.status == "pending",
        ):
            attempt.status = "canceled"
            attempt.attempted_at = now
            attempt.error_message = reason
            db.add(attempt)


def _pref_allows_category(category: str, alert_type: str, prefs: NotificationPreference | None) -> bool:
    if prefs is None:
        return True
    preference = get_notification_event(alert_type).global_preference
    if alert_type in {"LONG_RUSH", "LONG_RECEPTION", "LONG_PASS"} and not prefs.big_play_alerts:
        return False
    return bool(getattr(prefs, preference, True)) if preference else True


def _league_pref_allows(category: str, alert_type: str, pref: NotificationLeaguePreference | None) -> bool:
    if pref is None:
        return True
    if not pref.enabled:
        return False
    preference = get_notification_event(alert_type).league_preference
    if alert_type in {"LONG_RUSH", "LONG_RECEPTION", "LONG_PASS"} and not pref.big_play_alerts:
        return False
    return bool(getattr(pref, preference, True)) if preference else True


def _quiet_end(now: datetime, prefs: NotificationPreference) -> datetime | None:
    if not prefs.quiet_hours_start or not prefs.quiet_hours_end:
        return None
    try:
        start = time.fromisoformat(prefs.quiet_hours_start)
        end = time.fromisoformat(prefs.quiet_hours_end)
        zone = ZoneInfo(prefs.timezone)
    except (ValueError, ZoneInfoNotFoundError):
        return None
    local_now = now.astimezone(zone)
    local_time = local_now.timetz().replace(tzinfo=None)
    if start == end:
        return None
    in_quiet_hours = start <= local_time < end if start < end else local_time >= start or local_time < end
    if not in_quiet_hours:
        return None
    end_date = local_now.date()
    if start >= end and local_time >= start:
        end_date += timedelta(days=1)
    return datetime.combine(end_date, end, tzinfo=zone).astimezone(timezone.utc)


def _ensure_legacy_content(db: Session, row: ScheduledNotification) -> None:
    if row.event_key is None:
        row.event_key = f"legacy-scheduled:{row.id}"
    if row.title and row.body:
        return
    league = db.get(League, row.league_id)
    canonical_event_type = (row.event_type or row.notification_type).upper()
    row.event_type = canonical_event_type
    category, title, body = _event_metadata(canonical_event_type, row.payload or {}, league.name if league else "your league")
    row.category = category
    row.title = title
    row.body = body
    row.payload = {
        **(row.payload or {}),
        "league_id": row.league_id,
        "scope": row.scope if row.scope in NOTIFICATION_SCOPES else "direct_user",
        "destination": _destination_for(canonical_event_type, league_id=row.league_id, payload=row.payload or {}),
    }


def _ensure_in_app_attempt(db: Session, row: ScheduledNotification) -> None:
    exists = (
        db.query(NotificationDeliveryAttempt.id)
        .filter(NotificationDeliveryAttempt.scheduled_notification_id == row.id, NotificationDeliveryAttempt.channel == "in_app")
        .first()
    )
    if not exists:
        db.add(
            NotificationDeliveryAttempt(
                scheduled_notification_id=row.id, user_id=row.user_id, channel="in_app", attempt_number=1, status="pending"
            )
        )
        db.flush()


def _latest_attempts(db: Session, row: ScheduledNotification) -> dict[str, NotificationDeliveryAttempt]:
    attempts = (
        db.query(NotificationDeliveryAttempt)
        .filter(NotificationDeliveryAttempt.scheduled_notification_id == row.id)
        .order_by(NotificationDeliveryAttempt.channel, NotificationDeliveryAttempt.attempt_number.desc())
        .all()
    )
    latest: dict[str, NotificationDeliveryAttempt] = {}
    for attempt in attempts:
        latest.setdefault(attempt.channel, attempt)
    return latest


def _mark_attempt(
    db: Session,
    attempt: NotificationDeliveryAttempt,
    *,
    status: str,
    now: datetime,
    error_message: str | None = None,
    provider_message_id: str | None = None,
) -> None:
    attempt.status = status
    attempt.attempted_at = now
    attempt.error_message = _sanitized_error(error_message)
    attempt.provider_message_id = provider_message_id
    attempt.delivered_at = now if status == "delivered" else None
    attempt.provider_accepted_at = now if status == "provider_accepted" else None
    attempt.next_retry_at = None
    db.add(attempt)


def _sanitized_error(value: str | None) -> str | None:
    """Keep provider errors operationally useful without retaining payloads/secrets."""
    if not value:
        return None
    return " ".join(value.replace("\n", " ").replace("\r", " ").split())[:500]


def _heartbeat_claim(db: Session, row: ScheduledNotification, *, now: datetime, worker_id: str) -> None:
    if row.claimed_by != worker_id or row.status != "claimed":
        raise RuntimeError("notification claim was lost")
    row.claim_heartbeat_at = now
    db.add(row)
    db.flush()


def _schedule_retry(db: Session, attempt: NotificationDeliveryAttempt, *, now: datetime, error_message: str) -> None:
    _mark_attempt(db, attempt, status="retry", now=now, error_message=error_message)
    retry_index = min(attempt.attempt_number - 1, len(DELIVERY_RETRY_DELAYS) - 1)
    next_retry_at = now + DELIVERY_RETRY_DELAYS[retry_index]
    db.add(
        NotificationDeliveryAttempt(
            scheduled_notification_id=attempt.scheduled_notification_id,
            user_id=attempt.user_id,
            channel=attempt.channel,
            attempt_number=attempt.attempt_number + 1,
            status="pending",
            next_retry_at=next_retry_at,
        )
    )
    # The session deliberately disables autoflush. Persist the successor
    # attempt before recalculating the event state so a retry cannot be
    # mistaken for a completed delivery in this worker transaction.
    db.flush()


def _process_attempt(
    db: Session,
    *,
    row: ScheduledNotification,
    attempt: NotificationDeliveryAttempt,
    user: User,
    prefs: NotificationPreference | None,
    league_pref: NotificationLeaguePreference | None,
    now: datetime,
    push_provider: PushNotificationProvider,
    email_provider: EmailNotificationProvider,
    worker_id: str,
) -> None:
    if attempt.status != "pending" or (attempt.next_retry_at and _as_utc(attempt.next_retry_at) > now):
        return
    _heartbeat_claim(db, row, now=now, worker_id=worker_id)
    event_type = (row.event_type or row.notification_type).upper()
    # Category and league controls govern every notification surface,
    # including the in-app center. Delivery-channel controls below govern
    # only their corresponding external channel, so turning off push/email
    # does not erase an otherwise-enabled in-app notification.
    if not _pref_allows_category(row.category, event_type, prefs) or not _league_pref_allows(row.category, event_type, league_pref):
        _mark_attempt(db, attempt, status="skipped", now=now, error_message="disabled by notification preference")
        return
    if attempt.channel == "in_app":
        event_key = _event_key("in_app", row.event_key or f"legacy-scheduled:{row.id}")
        if db.query(NotificationLog.id).filter(NotificationLog.event_key == event_key).first() is None:
            db.add(
                NotificationLog(
                    user_id=user.id,
                    user_key=legacy_user_key(user.id),
                    league_id=row.league_id,
                    alert_type=event_type,
                    category=row.category,
                    scope=row.scope if row.scope in NOTIFICATION_SCOPES else "direct_user",
                    event_key=event_key,
                    title=row.title or "Notification",
                    body=row.body or "",
                    payload=row.payload or {},
                    sent_at=now,
                )
            )
            db.flush()
        _mark_attempt(db, attempt, status="delivered", now=now)
        return

    if attempt.channel == "push":
        if not settings.push_notifications_enabled or not (prefs is None or prefs.push_enabled):
            _mark_attempt(db, attempt, status="skipped", now=now, error_message="push delivery is disabled")
            return
        # The provider targets the stable external user identity rather than a
        # raw browser token. Still require an enabled local subscription so an
        # old OneSignal alias cannot receive a notification after a user has
        # removed every registered device from this application.
        if (
            db.query(PushToken.id)
            .filter(PushToken.user_id == user.id, PushToken.provider == "onesignal", PushToken.enabled.is_(True))
            .first()
            is None
        ):
            _mark_attempt(db, attempt, status="skipped", now=now, error_message="no active push subscription")
            return
        definition = get_notification_event(event_type)
        if definition.quiet_hours_apply and prefs:
            quiet_end = _quiet_end(now, prefs)
            if quiet_end:
                attempt.next_retry_at = quiet_end
                attempt.attempted_at = now
                attempt.error_message = "deferred for quiet hours"
                db.add(attempt)
                return
        try:
            result = push_provider.send(
                external_user_id=external_user_identity(user.id),
                title=row.title or "",
                body=row.body or "",
                data={"destination": (row.payload or {}).get("destination"), "event_type": event_type},
                idempotency_key=_provider_idempotency_key("push", row.event_key or f"legacy-scheduled:{row.id}"),
            )
        except Exception:
            if attempt.attempt_number < settings.notification_max_attempts:
                _schedule_retry(db, attempt, now=now, error_message="push provider request failed")
            else:
                _mark_attempt(db, attempt, status="failed", now=now, error_message="push provider request failed")
            return
    elif attempt.channel == "email":
        if not settings.email_enabled or not (prefs is None or prefs.email_enabled):
            _mark_attempt(db, attempt, status="skipped", now=now, error_message="email delivery is disabled")
            return
        try:
            result = email_provider.send(
                email=user.email,
                title=row.title or "",
                body=row.body or "",
                idempotency_key=_provider_idempotency_key("email", row.event_key or f"legacy-scheduled:{row.id}"),
            )
        except Exception:
            if attempt.attempt_number < settings.notification_max_attempts:
                _schedule_retry(db, attempt, now=now, error_message="email provider request failed")
            else:
                _mark_attempt(db, attempt, status="failed", now=now, error_message="email provider request failed")
            return
    else:
        _mark_attempt(db, attempt, status="failed", now=now, error_message="unsupported delivery channel")
        return

    if result.accepted:
        # Provider acceptance is not evidence that a browser, device, or
        # mailbox displayed the message. Keep that distinction durable.
        _mark_attempt(db, attempt, status="provider_accepted", now=now, provider_message_id=result.provider_message_id)
    elif result.retryable and attempt.attempt_number < settings.notification_max_attempts:
        _schedule_retry(db, attempt, now=now, error_message=result.error or "provider delivery failed")
    else:
        # Do not guess at an invalid token from a provider error body. Only
        # disable a subscription when a provider adapter identifies the exact
        # registered subscription ID; this keeps one stale browser from
        # incorrectly disabling another device for the same user.
        if result.invalid_subscription_id:
            (
                db.query(PushToken)
                .filter(
                    PushToken.user_id == user.id,
                    PushToken.device_token == result.invalid_subscription_id,
                )
                .update({PushToken.enabled: False}, synchronize_session=False)
            )
        _mark_attempt(db, attempt, status="failed", now=now, error_message=result.error or "provider delivery failed")


def _refresh_event_state(db: Session, row: ScheduledNotification, now: datetime) -> None:
    latest = _latest_attempts(db, row)
    if any(attempt.status == "pending" for attempt in latest.values()):
        next_times = [attempt.next_retry_at for attempt in latest.values() if attempt.status == "pending" and attempt.next_retry_at]
        row.status = "retry" if next_times else "pending"
        row.scheduled_for = min((_as_utc(value) for value in next_times), default=now)
        row.claimed_at = None
        row.claim_heartbeat_at = None
        row.claimed_by = None
    elif any(attempt.status == "failed" for attempt in latest.values()):
        row.status = "dead_letter"
        row.completed_at = now
        row.claimed_at = None
        row.claim_heartbeat_at = None
        row.claimed_by = None
        # sent_at remains null when any enabled channel could not be delivered.
        row.sent_at = None
    else:
        row.status = "provider_accepted" if any(attempt.status == "provider_accepted" for attempt in latest.values()) else "delivered"
        row.completed_at = now
        row.sent_at = now
        row.claimed_at = None
        row.claim_heartbeat_at = None
        row.claimed_by = None
    db.add(row)


def _claim_due_events(db: Session, *, now: datetime, worker_id: str, limit: int) -> list[int]:
    expired_claim = now - timedelta(seconds=settings.notification_claim_lease_seconds)
    rows = (
        db.query(ScheduledNotification)
        .filter(ScheduledNotification.canceled_at.is_(None))
        # Legacy rows created before the durable status column use sent_at as
        # their terminal marker. Retaining this guard prevents a deployment
        # race or a partial data migration from sending them a second time.
        .filter(ScheduledNotification.sent_at.is_(None))
        .filter(ScheduledNotification.scheduled_for <= now)
        .filter(
            or_(
                ScheduledNotification.status.in_(("pending", "retry")),
                and_(
                    ScheduledNotification.status == "claimed",
                    func.coalesce(ScheduledNotification.claim_heartbeat_at, ScheduledNotification.claimed_at) < expired_claim,
                ),
            )
        )
        .order_by(ScheduledNotification.scheduled_for.asc(), ScheduledNotification.id.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
        .all()
    )
    for row in rows:
        row.status = "claimed"
        row.claimed_at = now
        row.claim_heartbeat_at = now
        row.claimed_by = worker_id
        db.add(row)
    db.commit()
    return [row.id for row in rows]


def process_due_notifications_once(
    db: Session,
    *,
    worker_id: str = "notification_processor",
    now: datetime | None = None,
    limit: int = 100,
    push_provider: PushNotificationProvider | None = None,
    email_provider: EmailNotificationProvider | None = None,
) -> dict[str, int]:
    current = _as_utc(now or utcnow())
    push = push_provider or get_push_provider()
    email = email_provider or get_email_provider()
    claimed_ids = _claim_due_events(db, now=current, worker_id=worker_id, limit=max(1, min(limit, 500)))
    summary = {"claimed": len(claimed_ids), "delivered": 0, "provider_accepted": 0, "retried": 0, "failed": 0, "skipped": 0}
    for event_id in claimed_ids:
        row = (
            db.query(ScheduledNotification)
            .filter(ScheduledNotification.id == event_id, ScheduledNotification.status == "claimed", ScheduledNotification.claimed_by == worker_id)
            .with_for_update()
            .one_or_none()
        )
        if row is None:
            continue
        try:
            _ensure_legacy_content(db, row)
            _ensure_in_app_attempt(db, row)
            user = db.get(User, row.user_id)
            membership_exists = user is not None and (
                db.query(LeagueMember.id)
                .filter(LeagueMember.league_id == row.league_id, LeagueMember.user_id == user.id)
                .first()
                is not None
            )
            if user is None or not user.is_active or not membership_exists:
                row.status = "canceled"
                row.completed_at = current
                row.canceled_at = current
                row.claim_heartbeat_at = None
                row.claimed_at = None
                row.claimed_by = None
                for attempt in _latest_attempts(db, row).values():
                    if attempt.status == "pending":
                        _mark_attempt(db, attempt, status="canceled", now=current, error_message="recipient is no longer eligible")
                db.add(row)
                db.commit()
                summary["skipped"] += 1
                continue
            prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == user.id).one_or_none()
            league_pref = (
                db.query(NotificationLeaguePreference)
                .filter(NotificationLeaguePreference.user_id == user.id, NotificationLeaguePreference.league_id == row.league_id)
                .one_or_none()
            )
            for attempt in _latest_attempts(db, row).values():
                _process_attempt(
                    db,
                    row=row,
                    attempt=attempt,
                    user=user,
                    prefs=prefs,
                    league_pref=league_pref,
                    now=current,
                    push_provider=push,
                    email_provider=email,
                    worker_id=worker_id,
                )
            _refresh_event_state(db, row, current)
            db.commit()
            if row.status == "delivered":
                summary["delivered"] += 1
            elif row.status == "provider_accepted":
                # In-app delivery completed, while the provider has accepted
                # (but cannot prove display of) the external notification.
                summary["delivered"] += 1
                summary["provider_accepted"] += 1
            elif row.status == "dead_letter":
                summary["failed"] += 1
            elif row.status == "retry":
                summary["retried"] += 1
            else:
                summary["skipped"] += 1
        except Exception:
            db.rollback()
            # A worker failure must leave the lease recoverable. The next
            # worker pass reclaims it after the bounded lease interval.
    return summary


def notification_queue_health(db: Session) -> dict[str, int | str | None]:
    rows = db.query(ScheduledNotification.status, func.count(ScheduledNotification.id)).group_by(ScheduledNotification.status).all()
    counts = {str(status): int(count) for status, count in rows}
    last_delivery = db.query(func.max(NotificationDeliveryAttempt.delivered_at)).scalar()
    return {
        "pending": counts.get("pending", 0),
        "retry": counts.get("retry", 0),
        "dead_letter": counts.get("dead_letter", 0),
        "delivered": counts.get("delivered", 0),
        "last_successful_delivery_at": _as_utc(last_delivery).isoformat() if last_delivery else None,
    }


def record_delivery_attempt(
    db: Session,
    *,
    scheduled_notification_id: int,
    channel: str,
    status: str,
    error_message: str | None = None,
    delivered_at: datetime | None = None,
) -> NotificationDeliveryAttempt:
    """Compatibility helper used by existing tests and operational repair tools."""
    latest = (
        db.query(NotificationDeliveryAttempt)
        .filter(NotificationDeliveryAttempt.scheduled_notification_id == scheduled_notification_id, NotificationDeliveryAttempt.channel == channel)
        .order_by(NotificationDeliveryAttempt.attempt_number.desc())
        .first()
    )
    if latest is None:
        scheduled = db.get(ScheduledNotification, scheduled_notification_id)
        if scheduled is None:
            raise ValueError("scheduled notification does not exist")
        latest = NotificationDeliveryAttempt(
            scheduled_notification_id=scheduled.id, user_id=scheduled.user_id, channel=channel, attempt_number=1, status="pending"
        )
    now = _as_utc(delivered_at or utcnow())
    _mark_attempt(db, latest, status=status, now=now, error_message=error_message)
    row = db.get(ScheduledNotification, scheduled_notification_id)
    if row:
        _refresh_event_state(db, row, now)
    return latest


def create_test_alert(db: Session, current_user_id: int) -> NotificationRead:
    """Development/admin diagnostic event; the route controls production access."""
    league_id = db.query(LeagueMember.league_id).filter(LeagueMember.user_id == current_user_id).scalar()
    if league_id is None:
        raise ValueError("join a league before creating a test notification")
    event = queue_notification_event(
        db,
        league_id=league_id,
        user_id=current_user_id,
        event_type="PROJECTION",
        event_key=f"test-alert:{current_user_id}:{uuid5(NAMESPACE_URL, str(utcnow().timestamp()))}",
        payload={"source": "test"},
    )
    db.commit()
    # Test events use the same worker path. Return a temporary view that does
    # not pretend external delivery has occurred.
    return NotificationRead(
        id=event.id,
        alert_type=event.notification_type,
        title=event.title or "",
        body=event.body or "",
        payload=event.payload,
        sent_at=event.scheduled_for,
        category=event.category,
        event_type=event.event_type,
        scope=event.scope if event.scope in NOTIFICATION_SCOPES else "direct_user",
        destination=_validated_destination(event.payload),
    )
