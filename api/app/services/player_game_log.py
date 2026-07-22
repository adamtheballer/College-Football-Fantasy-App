import re

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.schemas.game_log import (
    PlayerGameLogRead,
    PlayerGameLogRowRead,
    PlayerGameLogStatRead,
)


TEAM_NAME_ALIASES = {
    "cal": "california",
    "california": "california",
    "miami fl": "miami",
    "miami florida": "miami",
    "nc state": "nc state",
    "north carolina state": "nc state",
    "ole miss": "ole miss",
    "mississippi": "ole miss",
    "pitt": "pitt",
    "pittsburgh": "pitt",
    "southern methodist": "smu",
    "smu": "smu",
    "central florida": "ucf",
    "ucf": "ucf",
}


def normalize_team_name(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("&", "and")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalized).split())


def canonical_team_name(value: str | None) -> str | None:
    normalized = normalize_team_name(value)
    if not normalized:
        return None
    return TEAM_NAME_ALIASES.get(normalized, normalized)


def _same_team(left: str | None, right: str | None) -> bool:
    return canonical_team_name(left) == canonical_team_name(right)


def _location_label(schedule: TeamSchedule) -> str:
    if schedule.is_bye:
        return "BYE"
    if schedule.location == "away":
        return "Away"
    if schedule.location == "neutral":
        return "Neutral"
    return "Home"


def _fantasy_points(stats: dict) -> float | None:
    for key in ("fantasy_points", "fantasyPoints", "fpts", "FantasyPoints"):
        value = stats.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _stat_read(stat: PlayerGameStat | PlayerStat | None) -> PlayerGameLogStatRead | None:
    if stat is None:
        return None
    return PlayerGameLogStatRead(
        source=stat.source,
        stats=stat.stats,
        fantasy_points=_fantasy_points(stat.stats),
        updated_at=stat.updated_at,
    )


def _team_schedule_table_exists(db: Session) -> bool:
    return inspect(db.get_bind()).has_table(TeamSchedule.__tablename__)


def _game_result(schedule: TeamSchedule, game: Game | None) -> str | None:
    if (
        schedule.is_bye
        or game is None
        or game.home_points is None
        or game.away_points is None
    ):
        return None

    if _same_team(schedule.team_name, game.home_team):
        team_points, opponent_points = game.home_points, game.away_points
    elif _same_team(schedule.team_name, game.away_team):
        team_points, opponent_points = game.away_points, game.home_points
    else:
        return None

    outcome = "W" if team_points > opponent_points else "L" if team_points < opponent_points else "T"
    return f"{outcome} {team_points}\u2013{opponent_points}"


def _game_status(schedule: TeamSchedule, game: Game | None, stat: PlayerGameStat | PlayerStat | None) -> str:
    if schedule.is_bye:
        return "bye"
    if _game_result(schedule, game) is not None:
        return "final"
    # A provider may publish in-progress player statistics before the team
    # final score is available.  Never describe that as a final game.
    return "active" if stat is not None else "scheduled"


def _stat_status(schedule: TeamSchedule, game: Game | None, stat: PlayerGameStat | PlayerStat | None) -> str:
    if schedule.is_bye:
        return "not_available"
    if _game_result(schedule, game) is not None:
        return "final" if stat is not None else "missing"
    return "active" if stat is not None else "scheduled"


def build_player_game_log(db: Session, player: Player, *, season: int) -> PlayerGameLogRead:
    if not _team_schedule_table_exists(db):
        return PlayerGameLogRead(
            player_id=player.id,
            player_name=player.name,
            season=season,
            team_name=player.school,
            position=player.position,
            games=[],
            message="The 2026 team schedule is not available yet.",
        )
    schedules = (
        db.query(TeamSchedule)
        .filter(TeamSchedule.season == season)
        .order_by(TeamSchedule.week.asc(), TeamSchedule.id.asc())
        .all()
    )
    player_schedules = [schedule for schedule in schedules if _same_team(schedule.team_name, player.school)]
    if not player_schedules:
        return PlayerGameLogRead(
            player_id=player.id,
            player_name=player.name,
            season=season,
            team_name=player.school,
            position=player.position,
            games=[],
            message="2026 schedule has not been imported for this player's team.",
        )

    game_ids = [schedule.game_id for schedule in player_schedules if schedule.game_id is not None]
    games_by_id = {
        game.id: game
        for game in db.query(Game).filter(Game.id.in_(game_ids or [-1])).all()
    }
    stats_by_game = {
        row.game_id: row
        for row in db.query(PlayerGameStat)
        .filter(PlayerGameStat.player_id == player.id, PlayerGameStat.game_id.in_(game_ids or [-1]))
        .all()
    }
    stats_by_week = {
        row.week: row
        for row in db.query(PlayerStat)
        .filter(
            PlayerStat.player_id == player.id,
            PlayerStat.season == season,
            PlayerStat.week.in_([schedule.week for schedule in player_schedules if not schedule.is_bye] or [-1]),
        )
        .all()
    }
    rows: list[PlayerGameLogRowRead] = []
    for schedule in player_schedules:
        game = games_by_id.get(schedule.game_id) if schedule.game_id is not None else None
        game_stat = stats_by_game.get(schedule.game_id) if schedule.game_id is not None else None
        stat = game_stat or stats_by_week.get(schedule.week)
        stat_read = _stat_read(stat)
        rows.append(
            PlayerGameLogRowRead(
                schedule_id=schedule.id,
                game_id=schedule.game_id,
                week=schedule.week,
                date=schedule.game_date,
                kickoff_at=schedule.kickoff_at,
                opponent_name=schedule.opponent_name,
                location=schedule.location,
                location_label=_location_label(schedule),
                neutral_site=schedule.neutral_site,
                conference_game=schedule.conference_game,
                venue=schedule.venue,
                tv_network=schedule.tv_network,
                game_status=_game_status(schedule, game, stat),
                stat_status=_stat_status(schedule, game, stat),
                result=_game_result(schedule, game),
                stats=stat_read,
            )
        )
    return PlayerGameLogRead(
        player_id=player.id,
        player_name=player.name,
        season=season,
        team_name=player.school,
        position=player.position,
        games=rows,
    )
