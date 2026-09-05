"""Read accepted, game-keyed box scores for cards; never mutate league scores."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll, ProviderGameSnapshot


@dataclass(frozen=True)
class PlayerGameFeed:
    state: str
    stats: dict | None
    source: str
    updated_at: datetime


def accepted_player_game_feed(
    db: Session, *, player_id: int, season: int, games: dict[int, Game],
) -> dict[int, PlayerGameFeed]:
    """Use exact event + accepted hash + internal player ID, not fantasy week.

    Includes players without a pregame projection. Rejected/out-of-order
    snapshots and other games in the same fantasy week cannot leak in.
    """
    event_games = {str(game.external_id): game.id for game in games.values() if game.external_id}
    if not event_games:
        return {}
    snapshots = db.query(
        ProviderGameSnapshot.provider_game_id,
        ProviderGameSnapshot.status,
        ProviderGameSnapshot.normalized_rows,
        ProviderGameSnapshot.provider_updated_at,
        ProviderGameSnapshot.captured_at,
    ).join(
        ProviderGamePoll,
        (ProviderGamePoll.provider == ProviderGameSnapshot.provider)
        & (ProviderGamePoll.provider_game_id == ProviderGameSnapshot.provider_game_id)
        & (ProviderGamePoll.accepted_snapshot_hash == ProviderGameSnapshot.snapshot_hash),
    ).filter(
        ProviderGameSnapshot.provider == "espn",
        ProviderGameSnapshot.season == season,
        ProviderGameSnapshot.provider_game_id.in_(event_games),
        ProviderGameSnapshot.accepted.is_(True),
        ProviderGameSnapshot.status.in_(("live", "final")),
    ).all()
    result = {}
    for snapshot in snapshots:
        stats = next((row["stats"] for row in (snapshot.normalized_rows or [])
                      if isinstance(row, dict) and str(row.get("player_id")) == str(player_id)
                      and isinstance(row.get("stats"), dict)), None)
        result[event_games[snapshot.provider_game_id]] = PlayerGameFeed(
            state=snapshot.status,
            stats=dict(stats) if stats is not None else None,
            source="espn_final_boxscore" if snapshot.status == "final" else "espn_live_boxscore",
            updated_at=snapshot.provider_updated_at or snapshot.captured_at,
        )
    return result


def matching_weekly_stat(stat: PlayerStat | None, game: Game | None) -> PlayerStat | None:
    """Legacy weekly fallback is usable only when its event does not conflict."""
    if stat is None:
        return None
    event_id = next((str(stat.stats[key]) for key in ("EventID", "event_id", "eventId")
                     if stat.stats.get(key) is not None), None)
    if event_id and (game is None or event_id != str(game.external_id)):
        return None
    return stat
