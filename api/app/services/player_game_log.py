import re

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.scoring_engine import calculate_score
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.historical_stats import canonical_historical_season_rows
from collegefootballfantasy_api.app.services.player_game_feed import PlayerGameFeed, accepted_player_game_feed, matching_weekly_stat
from collegefootballfantasy_api.app.schemas.game_log import (
    PlayerGameLogRead,
    PlayerGameLogRowRead,
    PlayerGameLogSeasonSummaryRead,
    PlayerGameLogSummaryStatRead,
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


def _stat_read(
    stat: PlayerGameStat | PlayerStat | PlayerGameFeed | None,
    *,
    position: str,
    scoring_rules: dict | None,
) -> PlayerGameLogStatRead | None:
    if stat is None:
        return None
    fantasy_points = _fantasy_points(stat.stats)
    if fantasy_points is None and scoring_rules is not None:
        # Canonical provider stats may still use source field names such as
        # PassingYards.  calculate_score normalizes them before applying the
        # selected league's scoring rules.
        fantasy_points = calculate_score(stat.stats or {}, position, scoring_rules).total
    return PlayerGameLogStatRead(
        source=stat.source,
        stats=stat.stats,
        fantasy_points=fantasy_points,
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


def _has_final_box_score(stat: PlayerGameStat | PlayerStat | None) -> bool:
    """Only the worker's final-game record can finalize a scoreless schedule row."""

    return isinstance(stat, PlayerGameStat) and stat.source == "espn_final_boxscore"


def _game_status(schedule: TeamSchedule, game: Game | None, stat: PlayerGameStat | PlayerStat | None) -> str:
    if schedule.is_bye:
        return "bye"
    if _game_result(schedule, game) is not None or _has_final_box_score(stat):
        return "final"
    # A provider may publish in-progress player statistics before the team
    # final score is available.  Never describe that as a final game.
    return "active" if stat is not None else "scheduled"


def _stat_status(schedule: TeamSchedule, game: Game | None, stat: PlayerGameStat | PlayerStat | None) -> str:
    if schedule.is_bye:
        return "not_available"
    if _game_result(schedule, game) is not None or _has_final_box_score(stat):
        return "final" if stat is not None else "missing"
    return "active" if stat is not None else "scheduled"


def _league_scoring_rules(db: Session, league_id: int | None) -> dict | None:
    if league_id is None:
        return None
    if db.get(League, league_id) is None:
        raise ValueError("league not found")
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).one_or_none()
    return settings.scoring_json if settings and settings.scoring_json else {}


def _selected_historical_rows(
    rows: list[PlayerHistoricalSeasonStat],
    season: int,
) -> list[PlayerHistoricalSeasonStat]:
    selected = [row for row in rows if row.season == season]
    # A provider may retain a separate postseason split. Prefer the complete
    # regular-season rows when available, rather than summing overlapping data.
    regular = [row for row in selected if row.season_type.strip().lower() == "regular"]
    return regular or selected


_SUMMARY_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "QB": (
        ("Completions", "passing_completions"),
        ("Attempts", "passing_attempts"),
        ("Pass Yds", "passing_yards"),
        ("Pass TD", "passing_touchdowns"),
        ("INT", "interceptions"),
        ("Rush Att", "rushing_attempts"),
        ("Rush Yds", "rushing_yards"),
        ("Rush TD", "rushing_touchdowns"),
        ("Fumbles", "fumbles"),
    ),
    "RB": (
        ("Rush Att", "rushing_attempts"),
        ("Rush Yds", "rushing_yards"),
        ("Rush TD", "rushing_touchdowns"),
        ("Receptions", "receptions"),
        ("Rec Yds", "receiving_yards"),
        ("Rec TD", "receiving_touchdowns"),
        ("Fumbles", "fumbles"),
    ),
    "WR": (
        ("Targets", "receiving_targets"),
        ("Receptions", "receptions"),
        ("Rec Yds", "receiving_yards"),
        ("Rec TD", "receiving_touchdowns"),
        ("Rush Att", "rushing_attempts"),
        ("Rush Yds", "rushing_yards"),
        ("Rush TD", "rushing_touchdowns"),
        ("Fumbles", "fumbles"),
    ),
    "TE": (
        ("Targets", "receiving_targets"),
        ("Receptions", "receptions"),
        ("Rec Yds", "receiving_yards"),
        ("Rec TD", "receiving_touchdowns"),
        ("Fumbles", "fumbles"),
    ),
    "K": (("FGM", "field_goals_made"), ("FGA", "field_goals_attempted"), ("XPM", "extra_points_made"), ("XPA", "extra_points_attempted"), ("Kicking points", "kick_points")),
}


def _season_summary(
    rows: list[PlayerHistoricalSeasonStat],
    *,
    position: str,
) -> PlayerGameLogSeasonSummaryRead | None:
    if not rows:
        return None

    teams = list(dict.fromkeys(row.team_name for row in rows if row.team_name))
    games = [row.games_played for row in rows if row.games_played is not None]
    starts = [row.games_started for row in rows if row.games_started is not None]
    stats: list[PlayerGameLogSummaryStatRead] = []
    fields = _SUMMARY_FIELDS.get(position.upper(), _SUMMARY_FIELDS["RB"])
    for label, field in fields:
        values = [getattr(row, field) for row in rows if getattr(row, field) is not None]
        if values:
            stats.append(PlayerGameLogSummaryStatRead(label=label, value=sum(values)))

    # A partial transfer season must not present its incomplete fantasy-point
    # sum as a complete total.
    fantasy_values = [row.fantasy_points for row in rows]
    fantasy_points = sum(fantasy_values) if fantasy_values and all(value is not None for value in fantasy_values) else None
    games_played = sum(games) if games else None
    return PlayerGameLogSeasonSummaryRead(
        teams=teams,
        games_played=games_played,
        games_started=sum(starts) if starts else None,
        stats=stats,
        fantasy_points=fantasy_points,
        fantasy_points_per_game=(round(fantasy_points / games_played, 2) if fantasy_points is not None and games_played else None),
    )


def _current_school_schedule_seasons(db: Session, player: Player) -> list[int]:
    if not _team_schedule_table_exists(db):
        return []
    return sorted(
        {
            schedule.season
            for schedule in db.query(TeamSchedule.season, TeamSchedule.team_name).all()
            if _same_team(schedule.team_name, player.school)
        },
        reverse=True,
    )


def _provider_event_id(stat: PlayerGameStat | PlayerStat | None) -> str | None:
    if stat is None:
        return None
    for key in ("EventID", "event_id", "eventId"):
        value = stat.stats.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _schedule_duplicate_key(schedule: TeamSchedule) -> tuple[object, ...]:
    """Identify impossible duplicate schedule rows without merging real games."""

    if schedule.is_bye:
        return ("bye", schedule.week)
    if schedule.game_date is not None and schedule.opponent_name:
        # A college team cannot play the same opponent twice on the same date.
        # This is the stable key for legacy Week 0/Week 1 duplicate imports.
        return (
            "dated-game",
            canonical_team_name(schedule.team_name),
            canonical_team_name(schedule.opponent_name),
            schedule.game_date.isoformat(),
        )
    if schedule.game_id is not None:
        return ("game-id", schedule.game_id)
    return ("schedule", schedule.id)


def _canonical_player_schedules(
    schedules: list[TeamSchedule],
    *,
    games_by_id: dict[int, Game],
    stats_by_game: dict[int, PlayerGameStat],
    stats_by_week: dict[int, PlayerStat],
) -> list[TeamSchedule]:
    """Return one schedule row per actual game, preferring verified evidence.

    Legacy imports may contain the same game twice under different week
    numbers. The player card must not show a phantom game simply because that
    stale row survived beside the canonical ESPN-linked schedule record.
    """

    canonical: dict[tuple[object, ...], TeamSchedule] = {}

    def priority(schedule: TeamSchedule) -> tuple[int, int, int, int, int]:
        game = games_by_id.get(schedule.game_id) if schedule.game_id is not None else None
        stat = (
            stats_by_game.get(schedule.game_id)
            if schedule.game_id is not None
            else None
        ) or stats_by_week.get(schedule.week)
        event_id = _provider_event_id(stat)
        game_event_id = str(game.external_id).strip() if game and game.external_id else ""
        return (
            int(bool(event_id and event_id == game_event_id)),
            int(stat is not None),
            int(game_event_id.isdecimal()),
            int(schedule.kickoff_at is not None),
            schedule.week,
        )

    for schedule in schedules:
        key = _schedule_duplicate_key(schedule)
        current = canonical.get(key)
        if current is None or priority(schedule) > priority(current):
            canonical[key] = schedule
    return sorted(canonical.values(), key=lambda schedule: (schedule.week, schedule.id))


def build_player_game_log(
    db: Session,
    player: Player,
    *,
    season: int | None,
    league_id: int | None = None,
) -> PlayerGameLogRead:
    scoring_rules = _league_scoring_rules(db, league_id)
    historical_rows = canonical_historical_season_rows(db, player_id=player.id)
    current_school_seasons = _current_school_schedule_seasons(db, player)
    available_seasons = sorted(
        {row.season for row in historical_rows} | set(current_school_seasons[:1]),
        reverse=True,
    )
    selected_season = season if season is not None else (available_seasons[0] if available_seasons else 2026)
    selected_history = _selected_historical_rows(historical_rows, selected_season)
    season_summary = _season_summary(selected_history, position=player.position)
    if not _team_schedule_table_exists(db):
        return PlayerGameLogRead(
            player_id=player.id,
            player_name=player.name,
            season=selected_season,
            team_name=player.school,
            position=player.position,
            available_seasons=available_seasons,
            season_summary=season_summary,
            games=[],
            message=f"The {selected_season} team schedule is not available yet.",
        )
    schedules = (
        db.query(TeamSchedule)
        .filter(TeamSchedule.season == selected_season)
        .order_by(TeamSchedule.week.asc(), TeamSchedule.id.asc())
        .all()
    )
    historical_teams = [row.team_name for row in selected_history if row.team_name]
    # Historical records name the team the player actually represented. Use the
    # current school only for the newest schedule season, preventing transfer
    # seasons from silently adopting the player's current-team schedule.
    schedule_teams = historical_teams or ([player.school] if selected_season in current_school_seasons[:1] else [])
    player_schedules = [
        schedule for schedule in schedules
        if any(_same_team(schedule.team_name, team_name) for team_name in schedule_teams)
    ]
    if not player_schedules:
        return PlayerGameLogRead(
            player_id=player.id,
            player_name=player.name,
            season=selected_season,
            team_name=", ".join(historical_teams) if historical_teams else player.school,
            position=player.position,
            available_seasons=available_seasons,
            season_summary=season_summary,
            games=[],
            message=f"No game log is available for {selected_season}; the schedule has not been imported for this player's recorded team.",
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
            PlayerStat.season == selected_season,
            PlayerStat.week.in_([schedule.week for schedule in player_schedules if not schedule.is_bye] or [-1]),
        )
        .all()
    }
    player_schedules = _canonical_player_schedules(
        player_schedules,
        games_by_id=games_by_id,
        stats_by_game=stats_by_game,
        stats_by_week=stats_by_week,
    )
    feeds = accepted_player_game_feed(db, player_id=player.id, season=selected_season, games=games_by_id)
    rows: list[PlayerGameLogRowRead] = []
    for schedule in player_schedules:
        game = games_by_id.get(schedule.game_id) if schedule.game_id is not None else None
        game_stat = stats_by_game.get(schedule.game_id) if schedule.game_id is not None else None
        feed = feeds.get(schedule.game_id) if not schedule.is_bye else None
        stat = game_stat or (feed if feed and feed.stats is not None else None) or matching_weekly_stat(stats_by_week.get(schedule.week), game)
        stat_read = _stat_read(stat, position=player.position, scoring_rules=scoring_rules)
        rows.append(
            PlayerGameLogRowRead(
                schedule_id=schedule.id,
                game_id=schedule.game_id,
                team_name=schedule.team_name,
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
                game_status=("active" if feed.state == "live" else "final") if feed else _game_status(schedule, game, stat),
                stat_status=(("active" if feed.state == "live" else "final") if stat is not None else "missing") if feed else _stat_status(schedule, game, stat),
                result=_game_result(schedule, game),
                stats=stat_read,
            )
        )
    return PlayerGameLogRead(
        player_id=player.id,
        player_name=player.name,
        season=selected_season,
        team_name=", ".join(dict.fromkeys(schedule.team_name for schedule in player_schedules)),
        position=player.position,
        available_seasons=available_seasons,
        season_summary=season_summary,
        games=rows,
    )
