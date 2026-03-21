from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.notification import (
    NotificationLeaguePreference,
    NotificationLog,
    NotificationPreference,
    PushToken,
)
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
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

router = APIRouter()


def _legacy_user_key(user_id: int) -> str:
    return str(user_id)


def _log_matches_user(log: NotificationLog, user_id: int) -> bool:
    if log.user_id is not None:
        return log.user_id == user_id
    return log.user_key == _legacy_user_key(user_id)


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


@router.post("/tokens", response_model=PushTokenRead)
def register_push_token(
    payload: PushTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PushTokenRead:
    existing = db.query(PushToken).filter(PushToken.device_token == payload.device_token).first()
    if existing:
        existing.user_id = current_user.id
        existing.user_key = _legacy_user_key(current_user.id)
        existing.platform = payload.platform
        existing.enabled = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    token = PushToken(
        user_id=current_user.id,
        user_key=_legacy_user_key(current_user.id),
        device_token=payload.device_token,
        platform=payload.platform,
        enabled=True,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferences:
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
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


@router.post("/preferences", response_model=NotificationPreferences)
def update_preferences(
    payload: NotificationPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferences:
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id, user_key=_legacy_user_key(current_user.id))
    else:
        prefs.user_id = current_user.id
        prefs.user_key = _legacy_user_key(current_user.id)
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


@router.get("/alerts", response_model=NotificationList)
def list_alerts(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationList:
    global_prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    rostered_player_rows = (
        db.query(RosterEntry.player_id, Team.league_id)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.owner_user_id == current_user.id)
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
        .filter(NotificationLeaguePreference.user_id == current_user.id)
        .all()
    }

    rows = db.query(NotificationLog).order_by(NotificationLog.sent_at.desc()).limit(limit * 8).all()
    data: list[NotificationRead] = []
    for row in rows:
        if not _log_matches_user(row, current_user.id):
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


@router.post("/alerts/test", response_model=NotificationRead)
def create_test_alert(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    roster_row = (
        db.query(RosterEntry.player_id, Team.league_id)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.owner_user_id == current_user.id)
        .first()
    )
    payload: dict[str, int | str] = {"source": "test"}
    if roster_row and roster_row[0] and roster_row[1]:
        payload["player_id"] = int(roster_row[0])
        payload["league_id"] = int(roster_row[1])
    alert = NotificationLog(
        user_id=current_user.id,
        user_key=_legacy_user_key(current_user.id),
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


@router.get("/league-preferences", response_model=LeagueNotificationPreferences)
def get_league_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueNotificationPreferences:
    memberships = (
        db.query(LeagueMember, League)
        .join(League, League.id == LeagueMember.league_id)
        .filter(LeagueMember.user_id == current_user.id)
        .all()
    )
    pref_by_league = {
        pref.league_id: pref
        for pref in db.query(NotificationLeaguePreference)
        .filter(NotificationLeaguePreference.user_id == current_user.id)
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


@router.post("/league-preferences", response_model=LeagueNotificationPreferences)
def update_league_preferences(
    payload: LeagueNotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueNotificationPreferences:
    allowed_league_ids = {
        row[0]
        for row in db.query(LeagueMember.league_id)
        .filter(LeagueMember.user_id == current_user.id)
        .all()
    }
    for item in payload.items:
        if item.league_id not in allowed_league_ids:
            continue
        pref = (
            db.query(NotificationLeaguePreference)
            .filter(
                NotificationLeaguePreference.user_id == current_user.id,
                NotificationLeaguePreference.league_id == item.league_id,
            )
            .first()
        )
        if not pref:
            pref = NotificationLeaguePreference(
                user_id=current_user.id,
                user_key=_legacy_user_key(current_user.id),
                league_id=item.league_id,
            )
        else:
            pref.user_id = current_user.id
            pref.user_key = _legacy_user_key(current_user.id)
        pref.enabled = item.enabled
        pref.injury_alerts = item.injury_alerts
        pref.big_play_alerts = item.big_play_alerts
        pref.projection_alerts = item.projection_alerts
        db.add(pref)
    db.commit()
    return get_league_preferences(db=db, current_user=current_user)
