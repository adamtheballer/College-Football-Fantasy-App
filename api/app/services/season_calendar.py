"""Immutable, schedule-certified fantasy season calendars.

This module deliberately does not consult the database or a live provider.
Postseason timing is a release artifact derived from a sealed schedule snapshot,
which makes the calendar reproducible and prevents a partial provider import
from silently moving a league's playoffs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

from collegefootballfantasy_api.app.services.power4 import canonical_school_name, list_playoff_eligible_schools
from collegefootballfantasy_api.app.services.postseason_topology import required_rounds


CALENDAR_POLICY_VERSION = "P4_FULL_COVERAGE_V2"
SEALED_SCHEDULE_FORMAT_VERSION = "SEALED_CFB_SCHEDULE_V1"
DEFAULT_SNAPSHOT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "season_calendars"
EXCLUDED_GAME_KINDS = frozenset({"bye", "cancelled", "conference_championship", "bowl", "cfp", "postseason"})
VALID_LOCATIONS = frozenset({"home", "away", "neutral"})


class SeasonCalendarCoverageError(ValueError):
    """Raised when a safe fantasy calendar cannot be certified."""


@dataclass(frozen=True)
class SealedScheduleRow:
    team: str
    week: int
    opponent: str | None
    location: str
    game_kind: str = "regular"
    status: str = "scheduled"
    kickoff_at: str | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "SealedScheduleRow":
        try:
            return cls(
                team=str(value["team"]),
                week=int(value["week"]),
                opponent=str(value["opponent"]) if value.get("opponent") else None,
                location=str(value.get("location") or "").strip().lower(),
                game_kind=str(value.get("game_kind") or "regular").strip().lower(),
                status=str(value.get("status") or "scheduled").strip().lower(),
                kickoff_at=str(value["kickoff_at"]) if value.get("kickoff_at") else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SeasonCalendarCoverageError("sealed schedule contains an invalid game row") from exc


@dataclass(frozen=True)
class SealedScheduleSnapshot:
    season: int
    source_identity: str
    source_revision: str
    source_sha256: str
    format_version: str
    rows: tuple[SealedScheduleRow, ...]


@dataclass(frozen=True)
class CertifiedSeasonCalendar:
    season: int
    playoff_team_count: int
    regular_season_start_week: int
    regular_season_end_week: int
    playoff_start_week: int
    championship_week: int
    max_rounds: int
    calendar_policy_version: str
    source_identity: str
    source_revision: str
    source_sha256: str
    source_format_version: str

    def as_dict(self) -> dict[str, int | str]:
        return asdict(self)


def _artifact_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_sealed_schedule_snapshot(season: int, *, directory: Path = DEFAULT_SNAPSHOT_DIRECTORY) -> SealedScheduleSnapshot:
    """Load one checked-in immutable source artifact, or fail closed.

    A source URL, database import, or provider response is intentionally not a
    fallback.  The release process must place and review this artifact first.
    """

    path = directory / f"{season}.json"
    if not path.is_file():
        raise SeasonCalendarCoverageError(
            f"sealed {season} schedule snapshot is unavailable; calendar certification is blocked"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SeasonCalendarCoverageError(f"sealed {season} schedule snapshot cannot be read") from exc
    if not isinstance(payload, dict) or int(payload.get("season", -1)) != season:
        raise SeasonCalendarCoverageError(f"sealed schedule artifact is not a {season} snapshot")
    if payload.get("format_version") != SEALED_SCHEDULE_FORMAT_VERSION:
        raise SeasonCalendarCoverageError("sealed schedule snapshot has an unsupported format version")
    source_identity = str(payload.get("source_identity") or "").strip()
    source_revision = str(payload.get("source_revision") or "").strip()
    raw_rows = payload.get("games")
    if not source_identity or not source_revision or not isinstance(raw_rows, list):
        raise SeasonCalendarCoverageError("sealed schedule snapshot is missing required provenance")
    if any(not isinstance(row, dict) for row in raw_rows):
        raise SeasonCalendarCoverageError("sealed schedule contains a non-object game row")
    return SealedScheduleSnapshot(
        season=season,
        source_identity=source_identity,
        source_revision=source_revision,
        source_sha256=_artifact_hash(path),
        format_version=SEALED_SCHEDULE_FORMAT_VERSION,
        rows=tuple(SealedScheduleRow.from_mapping(row) for row in raw_rows),
    )


def _is_eligible_regular_game(row: SealedScheduleRow) -> bool:
    return (
        row.location in VALID_LOCATIONS
        and row.game_kind not in EXCLUDED_GAME_KINDS
        and row.status not in {"cancelled", "canceled", "postponed"}
        and bool(row.opponent)
    )


def schedule_coverage(snapshot: SealedScheduleSnapshot) -> dict[str, Any]:
    """Return identifier-only proof inputs used by certification and audits."""

    expected = set(list_playoff_eligible_schools())
    rows_by_team_week: dict[tuple[str, int], list[SealedScheduleRow]] = defaultdict(list)
    unrecognized_teams: list[str] = []
    for row in snapshot.rows:
        school = canonical_school_name(row.team)
        if school not in expected:
            unrecognized_teams.append(row.team)
            continue
        rows_by_team_week[(school, row.week)].append(row)

    duplicate_keys = sorted(
        {f"{team}:week-{week}" for (team, week), values in rows_by_team_week.items() if len(values) != 1}
    )
    coverage_by_week: dict[int, set[str]] = defaultdict(set)
    invalid_by_week: dict[int, set[str]] = defaultdict(set)
    all_weeks = {row.week for row in snapshot.rows if row.week > 0}
    for (team, week), values in rows_by_team_week.items():
        if len(values) != 1:
            invalid_by_week[week].add(team)
            continue
        if _is_eligible_regular_game(values[0]):
            coverage_by_week[week].add(team)
        else:
            invalid_by_week[week].add(team)

    all_weeks.update(coverage_by_week)
    by_week: dict[int, dict[str, list[str]]] = {}
    for week in sorted(all_weeks):
        present = coverage_by_week.get(week, set())
        by_week[week] = {
            "covered": sorted(present),
            "missing": sorted(expected - present),
            "invalid": sorted(invalid_by_week.get(week, set())),
        }
    return {
        "eligible_schools": sorted(expected),
        "eligible_school_count": len(expected),
        "weeks": by_week,
        "duplicate_team_weeks": duplicate_keys,
        "unrecognized_teams": sorted(set(unrecognized_teams)),
    }


def _contiguous_windows(weeks: Iterable[int]) -> list[tuple[int, int]]:
    values = sorted(set(weeks))
    if not values:
        return []
    windows: list[tuple[int, int]] = []
    start = end = values[0]
    for week in values[1:]:
        if week == end + 1:
            end = week
            continue
        windows.append((start, end))
        start = end = week
    windows.append((start, end))
    return windows


def _latest_window(*, full_weeks: Iterable[int], round_count: int) -> tuple[int, int]:
    candidates = [
        (start, end)
        for start, end in _contiguous_windows(full_weeks)
        if end - start + 1 >= round_count
    ]
    if not candidates:
        raise SeasonCalendarCoverageError(
            f"no contiguous {round_count}-week full-coverage regular-season window is certified"
        )
    # Ending later is primary; choosing the latest possible start within a run
    # makes the championship land on the final broad slate, never during a
    # conference-championship or bowl week.
    _run_start, run_end = max(candidates, key=lambda item: item[1])
    return run_end - round_count + 1, run_end


def certify_season_calendar(snapshot: SealedScheduleSnapshot, playoff_team_count: int) -> CertifiedSeasonCalendar:
    rounds = required_rounds(playoff_team_count)
    coverage = schedule_coverage(snapshot)
    # A duplicate is contradictory schedule evidence. Do not silently select a
    # window that happens not to include it; this source requires correction.
    if coverage["duplicate_team_weeks"]:
        raise SeasonCalendarCoverageError("sealed schedule contains duplicate or contradictory team-week rows")
    full_weeks = [
        week
        for week, detail in coverage["weeks"].items()
        if not detail["missing"] and not detail["invalid"]
    ]
    start_week, championship_week = _latest_window(full_weeks=full_weeks, round_count=rounds)
    regular_end = start_week - 1
    if regular_end < 1:
        raise SeasonCalendarCoverageError("certified postseason leaves no regular-season weeks")
    return CertifiedSeasonCalendar(
        season=snapshot.season,
        playoff_team_count=playoff_team_count,
        regular_season_start_week=1,
        regular_season_end_week=regular_end,
        playoff_start_week=start_week,
        championship_week=championship_week,
        max_rounds=rounds,
        calendar_policy_version=CALENDAR_POLICY_VERSION,
        source_identity=snapshot.source_identity,
        source_revision=snapshot.source_revision,
        source_sha256=snapshot.source_sha256,
        source_format_version=snapshot.format_version,
    )


def calendar_for_season(season: int, playoff_team_count: int) -> CertifiedSeasonCalendar:
    return certify_season_calendar(load_sealed_schedule_snapshot(season), playoff_team_count)


def certification_report(snapshot: SealedScheduleSnapshot) -> dict[str, Any]:
    coverage = schedule_coverage(snapshot)
    result: dict[str, Any] = {
        "season": snapshot.season,
        "status": "blocked",
        "calendar_policy_version": CALENDAR_POLICY_VERSION,
        "source_identity": snapshot.source_identity,
        "source_revision": snapshot.source_revision,
        "source_sha256": snapshot.source_sha256,
        "source_format_version": snapshot.format_version,
        **coverage,
        "contiguous_full_coverage_windows": _contiguous_windows(
            week for week, detail in coverage["weeks"].items() if not detail["missing"] and not detail["invalid"]
        ),
        "selected_windows": {},
    }
    if coverage["duplicate_team_weeks"]:
        result["blocker"] = "duplicate or contradictory team-week rows"
        return result
    selected: dict[str, dict[str, int]] = {}
    try:
        for count in (2, 4, 6, 8):
            calendar = certify_season_calendar(snapshot, count)
            selected[str(count)] = {
                "playoff_start_week": calendar.playoff_start_week,
                "championship_week": calendar.championship_week,
                "regular_season_end_week": calendar.regular_season_end_week,
                "rounds": calendar.max_rounds,
            }
    except SeasonCalendarCoverageError as exc:
        result["blocker"] = str(exc)
        return result
    result["selected_windows"] = selected
    result["status"] = "certified"
    return result
