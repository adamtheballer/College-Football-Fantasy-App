"""Validation and persistence for canonical team schedule imports.

The importer intentionally owns team schedules, not player schedules.  A player
Game Log joins the player's school to these rows at read time, which prevents
the same schedule from being copied to every player on a team.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.player_game_log import canonical_team_name, normalize_team_name


EASTERN_TIME = ZoneInfo("America/New_York")
REQUIRED_COLUMNS = {
    "Season",
    "Conference",
    "Team",
    "Week",
    "Date",
    "Opponent",
    "Location",
    "Neutral Site",
    "Conference Game",
    "Time (ET)",
    "TV",
    "ESPN Schedule Hub",
    "Primary Source",
    "Date Confirmed",
}
VALID_LOCATIONS = {"HOME", "AWAY", "NEUTRAL", "BYE"}


def _text(value: object | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_team_name(value)).strip("-")


def _bool(value: object | None) -> bool:
    return (_text(value) or "").lower() in {"yes", "true", "1", "y"}


def _parse_date(value: object | None) -> date | None:
    text = _text(value)
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date format {text!r}")


def _parse_kickoff(game_date: date | None, value: object | None) -> datetime | None:
    time_text = _text(value)
    if game_date is None or time_text is None or time_text.upper() == "TBD":
        return None
    for pattern in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %I %p"):
        try:
            parsed = datetime.strptime(f"{game_date.isoformat()} {time_text.upper()}", pattern)
            return parsed.replace(tzinfo=EASTERN_TIME)
        except ValueError:
            continue
    raise ValueError(f"unsupported Eastern kickoff time {time_text!r}")


@dataclass(frozen=True)
class ScheduleSourceRow:
    row_number: int
    season: int
    conference: str
    team_name: str
    week: int
    game_date: date | None
    opponent_name: str | None
    location: str
    venue: str | None
    conference_game: bool
    kickoff_at: datetime | None
    tv_network: str | None
    source_url: str | None
    primary_source_url: str | None
    date_confirmed: bool

    @property
    def is_bye(self) -> bool:
        return self.location == "BYE"

    @property
    def neutral_site(self) -> bool:
        return self.location == "NEUTRAL"


@dataclass
class ScheduleImportReport:
    source_rows: int = 0
    valid_rows: int = 0
    bye_rows: int = 0
    invalid_rows: list[dict] = field(default_factory=list)
    duplicate_team_weeks: list[dict] = field(default_factory=list)
    reciprocal_conflicts: list[dict] = field(default_factory=list)
    unresolved_source_teams: list[dict] = field(default_factory=list)
    source_team_matches: list[dict] = field(default_factory=list)
    existing_game_conflicts: list[dict] = field(default_factory=list)
    inserted_schedules: int = 0
    updated_schedules: int = 0
    unchanged_schedules: int = 0
    inserted_games: int = 0
    updated_games: int = 0
    player_school_match_count: int = 0
    players_without_schedule_match: list[dict] = field(default_factory=list)
    schedule_schema_ready: bool | None = None
    planned_schedules: int = 0
    planned_games: int = 0
    applied: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def has_errors(self) -> bool:
        return bool(
            self.invalid_rows
            or self.duplicate_team_weeks
            or self.reciprocal_conflicts
            or self.existing_game_conflicts
        )


def parse_schedule_csv(csv_text: str, *, season: int) -> tuple[list[ScheduleSourceRow], ScheduleImportReport]:
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = set(reader.fieldnames or [])
    missing = sorted(REQUIRED_COLUMNS - fieldnames)
    if missing:
        raise ValueError(f"Schedule CSV is missing required columns: {', '.join(missing)}")

    report = ScheduleImportReport()
    rows: list[ScheduleSourceRow] = []
    keys: Counter[tuple[str, int, int]] = Counter()
    for row_number, raw in enumerate(reader, start=2):
        report.source_rows += 1
        try:
            season_value = _text(raw.get("Season"))
            if not season_value or not season_value.startswith(str(season)):
                raise ValueError(f"expected {season} season, received {season_value or 'blank'}")
            team_name = _text(raw.get("Team"))
            conference = _text(raw.get("Conference"))
            location = (_text(raw.get("Location")) or "").upper()
            week_text = _text(raw.get("Week"))
            if not team_name or not conference or not week_text:
                raise ValueError("team, conference, and week are required")
            week = int(week_text)
            if week < 0 or week > 30:
                raise ValueError(f"week {week} is outside the supported range")
            if location not in VALID_LOCATIONS:
                raise ValueError(f"unsupported location {location or 'blank'}")
            opponent_name = _text(raw.get("Opponent"))
            if location == "BYE":
                opponent_name = None
            elif opponent_name is None:
                raise ValueError("non-bye schedule row has no opponent")
            game_date = _parse_date(raw.get("Date"))
            if location != "BYE" and game_date is None:
                raise ValueError("non-bye schedule row has no date")
            source = ScheduleSourceRow(
                row_number=row_number,
                season=season,
                conference=conference,
                team_name=team_name,
                week=week,
                game_date=game_date,
                opponent_name=opponent_name,
                location=location,
                venue=None,
                conference_game=_bool(raw.get("Conference Game")),
                kickoff_at=_parse_kickoff(game_date, raw.get("Time (ET)")),
                tv_network=_text(raw.get("TV")),
                source_url=_text(raw.get("ESPN Schedule Hub")),
                primary_source_url=_text(raw.get("Primary Source")),
                date_confirmed=_bool(raw.get("Date Confirmed")),
            )
            rows.append(source)
            keys[(canonical_team_name(team_name) or "", season, week)] += 1
            report.valid_rows += 1
            if source.is_bye:
                report.bye_rows += 1
        except (TypeError, ValueError) as exc:
            report.invalid_rows.append({"row_number": row_number, "error": str(exc), "row": raw})

    for (team_name, row_season, week), count in keys.items():
        if count > 1:
            report.duplicate_team_weeks.append(
                {"team_name": team_name, "season": row_season, "week": week, "count": count}
            )
    return rows, report


def validate_reciprocal_games(rows: list[ScheduleSourceRow], report: ScheduleImportReport) -> None:
    power_four_names = {canonical_team_name(row.team_name) for row in rows}
    by_team_week = {(canonical_team_name(row.team_name), row.week): row for row in rows}
    for row in rows:
        opponent_key = canonical_team_name(row.opponent_name)
        if row.is_bye or opponent_key not in power_four_names:
            continue
        counterpart = by_team_week.get((opponent_key, row.week))
        if counterpart is None or canonical_team_name(counterpart.opponent_name) != canonical_team_name(row.team_name):
            report.reciprocal_conflicts.append(
                {"row_number": row.row_number, "team": row.team_name, "week": row.week, "error": "missing reciprocal P4 game row"}
            )
            continue
        expected_locations = {row.location, counterpart.location}
        valid_locations = {"NEUTRAL"} if row.location == "NEUTRAL" else {"HOME", "AWAY"}
        if expected_locations != valid_locations or row.game_date != counterpart.game_date:
            report.reciprocal_conflicts.append(
                {
                    "row_number": row.row_number,
                    "team": row.team_name,
                    "week": row.week,
                    "error": "reciprocal game rows disagree on location or date",
                }
            )


def _external_game_id(row: ScheduleSourceRow) -> str:
    if row.is_bye or row.opponent_name is None:
        raise ValueError("Bye rows do not create games")
    if row.location == "HOME":
        home_team, away_team = row.team_name, row.opponent_name
    elif row.location == "AWAY":
        home_team, away_team = row.opponent_name, row.team_name
    else:
        home_team, away_team = sorted((row.team_name, row.opponent_name), key=normalize_team_name)
    return f"sheet-{row.season}-w{row.week}-{_slug(home_team)}-vs-{_slug(away_team)}"


def _game_teams(row: ScheduleSourceRow) -> tuple[str, str]:
    if row.opponent_name is None:
        raise ValueError("Bye rows do not create games")
    if row.location == "HOME":
        return row.team_name, row.opponent_name
    if row.location == "AWAY":
        return row.opponent_name, row.team_name
    return tuple(sorted((row.team_name, row.opponent_name), key=normalize_team_name))


def _game_values(row: ScheduleSourceRow) -> dict:
    home_team, away_team = _game_teams(row)
    return {
        "season": row.season,
        "week": row.week,
        "season_type": "regular",
        "start_date": row.kickoff_at,
        "home_team": home_team,
        "away_team": away_team,
        "neutral_site": row.neutral_site,
    }


def _game_identity(row: ScheduleSourceRow) -> tuple[int, int, bool, str, str]:
    home_team, away_team = _game_teams(row)
    return (
        row.season,
        row.week,
        row.neutral_site,
        canonical_team_name(home_team) or "",
        canonical_team_name(away_team) or "",
    )


def _sync_games(
    db: Session,
    rows: list[ScheduleSourceRow],
    report: ScheduleImportReport,
    *,
    apply: bool,
) -> dict[str, Game]:
    """Resolve source games against existing canonical games before creating any.

    The spreadsheet contains a row for each participating team.  A source
    external id is useful for imported-only games, but cannot be the only
    matching key because a provider game may already have a different id.
    """
    source_rows_by_external_id: dict[str, ScheduleSourceRow] = {}
    for row in rows:
        if not row.is_bye:
            source_rows_by_external_id.setdefault(_external_game_id(row), row)

    if not source_rows_by_external_id:
        return {}

    existing_by_external_id = {
        game.external_id: game
        for game in db.query(Game)
        .filter(Game.external_id.in_(list(source_rows_by_external_id)))
        .all()
        if game.external_id is not None
    }
    existing_by_identity: dict[tuple[int, int, bool, str, str], list[Game]] = defaultdict(list)
    for game in db.query(Game).filter(Game.season == rows[0].season if rows else -1).all():
        identity = (
            game.season,
            game.week,
            game.neutral_site,
            canonical_team_name(game.home_team) or "",
            canonical_team_name(game.away_team) or "",
        )
        existing_by_identity[identity].append(game)

    resolved: dict[str, Game] = {}
    for external_id, row in source_rows_by_external_id.items():
        values = _game_values(row)
        natural_matches = existing_by_identity.get(_game_identity(row), [])
        external_match = existing_by_external_id.get(external_id)
        candidates = {game.id: game for game in natural_matches}
        if external_match is not None:
            candidates[external_match.id] = external_match
        if len(candidates) > 1:
            report.existing_game_conflicts.append(
                {
                    "external_id": external_id,
                    "season": row.season,
                    "week": row.week,
                    "team": row.team_name,
                    "opponent": row.opponent_name,
                    "game_ids": sorted(candidates),
                    "error": "multiple existing games match the source game identity",
                }
            )
            continue
        game = next(iter(candidates.values()), None)
        if game is None:
            report.planned_games += 1
            if apply:
                game = Game(external_id=external_id, **values)
                db.add(game)
                existing_by_external_id[external_id] = game
                existing_by_identity[_game_identity(row)].append(game)
                report.inserted_games += 1
            else:
                continue
        elif any(getattr(game, key) != value for key, value in values.items()):
            # Preserve an existing provider external id.  The schedule source
            # only fills canonical matchup fields and must not replace it.
            report.updated_games += 1 if apply else 0
            if apply:
                for key, value in values.items():
                    setattr(game, key, value)
        resolved[external_id] = game
    if apply:
        db.flush()
    return resolved


def _schedule_values(row: ScheduleSourceRow, game_id: int | None) -> dict:
    return {
        "season": row.season,
        "week": row.week,
        "game_id": game_id,
        "opponent_name": row.opponent_name,
        "location": row.location.lower(),
        "is_bye": row.is_bye,
        "game_date": row.game_date,
        "kickoff_at": row.kickoff_at,
        "neutral_site": row.neutral_site,
        "conference_game": row.conference_game,
        "venue": row.venue,
        "tv_network": row.tv_network,
        "source_url": row.source_url,
        "primary_source_url": row.primary_source_url,
        "date_confirmed": row.date_confirmed,
    }


def _record_player_schedule_coverage(db: Session, rows: list[ScheduleSourceRow], report: ScheduleImportReport) -> None:
    schedule_teams = {canonical_team_name(row.team_name) for row in rows}
    players = db.query(Player.id, Player.name, Player.school).all()
    schools_by_canonical_name: dict[str, set[str]] = defaultdict(set)
    for _player_id, _player_name, school in players:
        canonical = canonical_team_name(school)
        if canonical:
            schools_by_canonical_name[canonical].add(school)

    for source_team in sorted({row.team_name for row in rows}, key=canonical_team_name):
        canonical = canonical_team_name(source_team)
        database_schools = sorted(schools_by_canonical_name.get(canonical or "", set()))
        if not database_schools:
            # The source is authoritative for every Power Four schedule, even
            # when the current player pool has nobody from that school.  Keep
            # this as an explicit coverage warning rather than blocking the
            # team-level import or inventing a player/team mapping.
            report.unresolved_source_teams.append(
                {
                    "source_team": source_team,
                    "canonical_team": canonical,
                    "warning": "no existing player school matches this source team",
                }
            )
            continue
        report.source_team_matches.append(
            {
                "source_team": source_team,
                "database_schools": database_schools,
                "match_method": "exact_canonical_name",
                "confidence": "deterministic",
            }
        )

    for player_id, player_name, school in players:
        if canonical_team_name(school) in schedule_teams:
            report.player_school_match_count += 1
        else:
            report.players_without_schedule_match.append(
                {"player_id": player_id, "player_name": player_name, "school": school}
            )


def _team_schedule_table_exists(db: Session) -> bool:
    return inspect(db.get_bind()).has_table(TeamSchedule.__tablename__)


def import_team_schedule_rows(
    db: Session,
    rows: list[ScheduleSourceRow],
    report: ScheduleImportReport,
    *,
    apply: bool,
) -> ScheduleImportReport:
    validate_reciprocal_games(rows, report)
    _record_player_schedule_coverage(db, rows, report)
    if report.has_errors:
        return report

    report.schedule_schema_ready = _team_schedule_table_exists(db)
    if not report.schedule_schema_ready:
        report.planned_schedules = len(rows)
        report.planned_games = len({_external_game_id(row) for row in rows if not row.is_bye})
        if apply:
            raise RuntimeError(
                "team_schedules is unavailable. Run the 0055_team_schedule_game_logs migration before importing."
            )
        return report

    existing = {
        (canonical_team_name(schedule.team_name), schedule.season, schedule.week): schedule
        for schedule in db.query(TeamSchedule).filter(TeamSchedule.season == rows[0].season if rows else -1).all()
    }
    games_by_external_id = _sync_games(db, rows, report, apply=apply)
    if report.has_errors:
        return report
    for row in rows:
        game = games_by_external_id.get(_external_game_id(row)) if not row.is_bye else None
        game_id = game.id if game else None
        key = (canonical_team_name(row.team_name), row.season, row.week)
        schedule = existing.get(key)
        values = _schedule_values(row, game_id)
        if schedule is None:
            report.planned_schedules += 1
            if apply:
                db.add(TeamSchedule(team_name=row.team_name, **values))
                report.inserted_schedules += 1
            continue
        current_values = {key: getattr(schedule, key) for key in values}
        expected_values = values
        if not apply and not row.is_bye:
            expected_values = {**values, "game_id": schedule.game_id}
        if current_values == expected_values and schedule.team_name == row.team_name:
            report.unchanged_schedules += 1
            continue
        report.updated_schedules += 1
        if apply:
            schedule.team_name = row.team_name
            for key, value in values.items():
                setattr(schedule, key, value)
    if apply:
        db.commit()
        report.applied = True
    return report
