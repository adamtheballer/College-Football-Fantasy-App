from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.notification_service import create_notification_event
from collegefootballfantasy_api.app.services.watchlist_alerts import notify_watchlisted_player


def notify_injury_change(
    db: Session,
    *,
    player_id: int,
    player_name: str,
    old_status: str | None,
    new_status: str,
    injury_id: int,
    league_id: int | None = None,
    is_starter: bool = False,
) -> int:
    status_changed = (old_status or "").upper() != new_status.upper()
    if not status_changed:
        return 0

    roster_rows = (
        db.query(Team.owner_user_id, Team.league_id, RosterEntry.slot)
        .join(RosterEntry, RosterEntry.team_id == Team.id)
        .filter(RosterEntry.player_id == player_id, Team.owner_user_id.isnot(None))
        .all()
    )

    notifications = 0
    recipients: set[tuple[int, int | None, str]] = set()
    for user_id, row_league_id, slot in roster_rows:
        if league_id is not None and row_league_id != league_id:
            continue
        category = "lineup_lock_warning" if is_starter or (slot or "").upper() not in {"BENCH", "IR"} else "player_injury"
        recipients.add((int(user_id), int(row_league_id), category))

    for user_id, row_league_id, alert_type in recipients:
        created = create_notification_event(
            db,
            user_id=user_id,
            league_id=row_league_id,
            alert_type=alert_type,
            title=f"{player_name} injury update",
            body=f"{player_name} changed from {old_status or 'UNKNOWN'} to {new_status}.",
            payload={"player_id": player_id, "old_status": old_status, "new_status": new_status},
            dedupe_key=f"injury:{injury_id}:{user_id}:{old_status}:{new_status}",
            source_entity_type="injury",
            source_entity_id=injury_id,
            deep_link="/injury-center",
        )
        if created:
            notifications += 1
    notifications += notify_watchlisted_player(
        db,
        player_id=player_id,
        league_id=league_id,
        alert_kind="injury_update",
        title=f"{player_name} injury update",
        body=f"{player_name} changed from {old_status or 'UNKNOWN'} to {new_status}.",
        payload={"old_status": old_status, "new_status": new_status},
        source_entity_type="injury",
        source_entity_id=injury_id,
    )
    return notifications
