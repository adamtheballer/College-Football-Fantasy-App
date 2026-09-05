"""Player-scoped display state for early games without changing league weeks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.player_game_log import canonical_team_name
from collegefootballfantasy_api.app.services.player_game_feed import PlayerGameFeed, accepted_player_game_feed, matching_weekly_stat


PRE_KICKOFF_TRANSITION = timedelta(hours=24)
INACTIVE_SCHEDULE_STATUSES = {"cancelled", "canceled", "postponed"}


@dataclass(frozen=True)
class PlayerGameDisplayState:
    state: str
    season: int | None = None
    week: int | None = None
    game_id: int | None = None
    opponent_name: str | None = None
    kickoff_at: datetime | None = None
    transition_at: datetime | None = None
    stats: dict | None = None
    source: str | None = None
    updated_at: datetime | None = None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _same_team(left: str | None, right: str | None) -> bool:
    return canonical_team_name(left) == canonical_team_name(right)


def _final_game(game: Game | None, stat: PlayerGameStat | None) -> bool:
    return bool(
        (game is not None and game.home_points is not None and game.away_points is not None)
        or (stat is not None and stat.source == "espn_final_boxscore")
    )


def player_game_display_state(
    db: Session,
    *,
    player: Player,
    season: int,
    now: datetime | None = None,
) -> PlayerGameDisplayState:
    """Choose this player's live, completed, or upcoming real-game context.

    This deliberately reads football schedule timestamps and never consults a
    fantasy matchup week. A final result remains visible until exactly 24
    hours before the player's next actual kickoff; history is never altered.
    """

    current = _as_utc(now) or datetime.now(timezone.utc)
    schedules = [
        row
        for row in db.query(TeamSchedule)
        .filter(TeamSchedule.season == season)
        .order_by(TeamSchedule.week.asc(), TeamSchedule.id.asc())
        .all()
        if _same_team(row.team_name, player.school)
    ]
    if not schedules:
        return PlayerGameDisplayState(state="unavailable", season=season)

    game_ids = [row.game_id for row in schedules if row.game_id is not None]
    games = {
        game.id: game
        for game in db.query(Game).filter(Game.id.in_(game_ids or [-1])).all()
    }
    game_stats = {
        stat.game_id: stat
        for stat in db.query(PlayerGameStat)
        .filter(PlayerGameStat.player_id == player.id, PlayerGameStat.game_id.in_(game_ids or [-1]))
        .all()
    }
    weekly_stats = {
        stat.week: stat
        for stat in db.query(PlayerStat)
        .filter(PlayerStat.player_id == player.id, PlayerStat.season == season)
        .all()
    }
    feeds = accepted_player_game_feed(db, player_id=player.id, season=season, games=games)

    completed: tuple[TeamSchedule, PlayerGameStat | PlayerStat | PlayerGameFeed | None] | None = None
    upcoming: TeamSchedule | None = None
    active: tuple[TeamSchedule, PlayerGameStat | PlayerStat | PlayerGameFeed | None, str] | None = None
    for schedule in schedules:
        if schedule.is_bye or schedule.location == "bye":
            continue
        game = games.get(schedule.game_id) if schedule.game_id is not None else None
        game_stat = game_stats.get(schedule.game_id) if schedule.game_id is not None else None
        feed = feeds.get(schedule.game_id)
        stat = game_stat or (feed if feed and feed.stats is not None else None) or matching_weekly_stat(weekly_stats.get(schedule.week), game)
        if _final_game(game, game_stat) or (feed and feed.state == "final"):
            if completed is None or (_as_utc(schedule.kickoff_at) or datetime.min.replace(tzinfo=timezone.utc)) > (_as_utc(completed[0].kickoff_at) or datetime.min.replace(tzinfo=timezone.utc)):
                completed = (schedule, stat)
            continue
        kickoff = _as_utc(schedule.kickoff_at)
        status = (game.schedule_status if game else "") or ""
        if status.casefold() in INACTIVE_SCHEDULE_STATUSES:
            continue
        if (feed and feed.state == "live") or status.casefold() in {"live", "in", "in_progress"}:
            active = (schedule, stat, "live")
        elif kickoff is not None and kickoff <= current < kickoff + timedelta(hours=12) and active is None:
            # Do not skip to next week while awaiting the first provider poll.
            # A clock alone cannot prove that play has actually started.
            active = (schedule, stat, "awaiting_live")
        if kickoff is not None and kickoff > current and status.casefold() not in INACTIVE_SCHEDULE_STATUSES:
            if upcoming is None or kickoff < (_as_utc(upcoming.kickoff_at) or datetime.max.replace(tzinfo=timezone.utc)):
                upcoming = schedule

    if active is not None:
        schedule, stat, state = active
        return PlayerGameDisplayState(
            state=state, season=season, week=schedule.week, game_id=schedule.game_id,
            opponent_name=schedule.opponent_name, kickoff_at=_as_utc(schedule.kickoff_at),
            stats=dict(stat.stats) if stat is not None else None,
            source=stat.source if stat is not None else None,
            updated_at=stat.updated_at if stat is not None else None,
        )

    if upcoming is not None:
        kickoff = _as_utc(upcoming.kickoff_at)
        assert kickoff is not None
        transition = kickoff - PRE_KICKOFF_TRANSITION
        if completed is None or current >= transition:
            return PlayerGameDisplayState(
                state="upcoming",
                season=season,
                week=upcoming.week,
                game_id=upcoming.game_id,
                opponent_name=upcoming.opponent_name,
                kickoff_at=kickoff,
                transition_at=transition,
            )

    if completed is not None:
        schedule, stat = completed
        return PlayerGameDisplayState(
            state="completed",
            season=season,
            week=schedule.week,
            game_id=schedule.game_id,
            opponent_name=schedule.opponent_name,
            kickoff_at=_as_utc(schedule.kickoff_at),
            transition_at=(
                (_as_utc(upcoming.kickoff_at) - PRE_KICKOFF_TRANSITION)
                if upcoming is not None and _as_utc(upcoming.kickoff_at) is not None
                else None
            ),
            stats=dict(stat.stats) if stat is not None else None,
            source=stat.source if stat is not None else None,
            updated_at=stat.updated_at if stat is not None else None,
        )
    return PlayerGameDisplayState(state="unavailable", season=season)
