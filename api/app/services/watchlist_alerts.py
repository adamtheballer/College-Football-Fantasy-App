from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.watchlist import Watchlist, WatchlistPlayer
from collegefootballfantasy_api.app.services.notification_service import create_notification_event


ALERT_TYPE_TO_FIELD = {
    "available_after_waiver": "alert_available",
    "injury_update": "alert_injury",
    "projection_jump": "alert_projection",
    "ownership_change": "alert_ownership",
    "good_matchup": "alert_matchup",
}


def notify_watchlisted_player(
    db: Session,
    *,
    player_id: int,
    alert_kind: str,
    title: str,
    body: str,
    payload: dict | None = None,
    league_id: int | None = None,
    source_entity_type: str = "player",
    source_entity_id: int | None = None,
) -> int:
    preference_field = ALERT_TYPE_TO_FIELD.get(alert_kind)
    if not preference_field:
        raise ValueError(f"unsupported watchlist alert kind: {alert_kind}")
    player = db.get(Player, player_id)
    rows = (
        db.query(WatchlistPlayer, Watchlist)
        .join(Watchlist, Watchlist.id == WatchlistPlayer.watchlist_id)
        .filter(WatchlistPlayer.player_id == player_id)
        .all()
    )
    count = 0
    for item, watchlist in rows:
        if league_id is not None and watchlist.league_id not in {None, league_id}:
            continue
        if not getattr(item, preference_field):
            continue
        notification = create_notification_event(
            db,
            user_id=watchlist.user_id,
            league_id=watchlist.league_id,
            alert_type="player_injury" if alert_kind == "injury_update" else "projection_update",
            title=title,
            body=body,
            payload={
                "player_id": player_id,
                "player_name": player.name if player else None,
                "watchlist_id": watchlist.id,
                "alert_kind": alert_kind,
                **(payload or {}),
            },
            dedupe_key=f"watchlist:{alert_kind}:{watchlist.user_id}:{watchlist.id}:{player_id}:{source_entity_id or 'event'}",
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id or player_id,
            deep_link=f"/league/{watchlist.league_id}/watchlist" if watchlist.league_id else "/watchlists",
        )
        if notification:
            count += 1
    return count
