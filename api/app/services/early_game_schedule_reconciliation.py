"""Repair early player-game schedule rows without touching fantasy league weeks.

The sealed calendar is the authority for a team's Week 0 football game.  A
legacy import could number that game as Week 1, which hides the next actual
Week 1 opponent and prevents the player-card schedule from selecting it.  This
module reconciles only teams that have a real Week 0 game in that calendar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import re

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.player_game_log import canonical_team_name
from collegefootballfantasy_api.app.services.season_calendar import (
    SealedScheduleRow,
    load_sealed_schedule_snapshot,
)


class EarlyGameScheduleReconciliationError(RuntimeError):
    """Raised when an early-game repair cannot be proven safe."""


@dataclass(frozen=True)
class EarlyGameScheduleReconciliationReport:
    season: int
    applied: bool
    repaired_teams: tuple[str, ...]
    created_next_games: int
    created_next_schedules: int
    moved_player_game_stats: int
    moved_player_stats: int
    unresolved: tuple[str, ...]


def _same_team(left: str | None, right: str | None) -> bool:
    return canonical_team_name(left) == canonical_team_name(right)


def _same_opponent(schedule: TeamSchedule, expected: SealedScheduleRow) -> bool:
    return _same_team(schedule.team_name, expected.team) and _same_team(schedule.opponent_name, expected.opponent)


def _calendar_date_and_kickoff(value: str | None) -> tuple[date | None, datetime | None]:
    if not value:
        return None, None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.date(), None
    return parsed.date(), parsed.astimezone(UTC)


def _event_id(*, season: int, week: int, team: str, opponent: str) -> str:
    slug = lambda value: re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return f"sealed-{season}-w{week}-{slug(team)}-{slug(opponent)}"[:64]


def _real_week_zero_rows(season: int) -> list[SealedScheduleRow]:
    return [
        row
        for row in load_sealed_schedule_snapshot(season).rows
        if row.week == 0 and row.opponent and row.location in {"home", "away", "neutral"}
    ]


def _next_regular_row(*, season: int, team: str) -> SealedScheduleRow:
    matches = [
        row
        for row in load_sealed_schedule_snapshot(season).rows
        if _same_team(row.team, team)
        and row.week == 1
        and row.opponent
        and row.location in {"home", "away", "neutral"}
    ]
    if len(matches) != 1:
        raise EarlyGameScheduleReconciliationError(
            f"sealed calendar must contain exactly one Week 1 regular game for {team}"
        )
    return matches[0]


def _find_early_schedule(
    schedules: list[TeamSchedule],
    *,
    expected: SealedScheduleRow,
) -> TeamSchedule | None:
    matches = [row for row in schedules if _same_opponent(row, expected)]
    if len(matches) > 1:
        raise EarlyGameScheduleReconciliationError(
            f"ambiguous schedule rows for {expected.team} vs {expected.opponent}"
        )
    return matches[0] if matches else None


def _move_compatibility_stats_to_week_zero(
    db: Session,
    *,
    game_id: int,
    season: int,
    old_week: int,
) -> tuple[int, int]:
    if old_week == 0:
        return 0, 0
    game_stats = db.query(PlayerGameStat).filter(
        PlayerGameStat.game_id == game_id,
        PlayerGameStat.season == season,
    ).all()
    player_ids = [row.player_id for row in game_stats]
    compatibility_rows = {
        row.player_id: row
        for row in db.query(PlayerStat).filter(
            PlayerStat.season == season,
            PlayerStat.week == old_week,
            PlayerStat.player_id.in_(player_ids or [-1]),
        ).all()
    }
    existing_week_zero = {
        row.player_id: row
        for row in db.query(PlayerStat).filter(
            PlayerStat.season == season,
            PlayerStat.week == 0,
            PlayerStat.player_id.in_(player_ids or [-1]),
        ).all()
    }
    for player_id in set(compatibility_rows) & set(existing_week_zero):
        raise EarlyGameScheduleReconciliationError(
            f"player {player_id} already has both Week 0 and Week {old_week} compatibility stats"
        )
    for row in game_stats:
        row.week = 0
    for row in compatibility_rows.values():
        row.week = 0
    return len(game_stats), len(compatibility_rows)


def reconcile_early_player_game_schedules(
    db: Session,
    *,
    season: int,
    apply: bool,
) -> EarlyGameScheduleReconciliationReport:
    """Reconcile real Week 0 teams and their immediate next game.

    This intentionally modifies ``Game``/``TeamSchedule`` and player-stat week
    labels only. It neither queries nor writes league matchups, rosters,
    standings, scoring, or notifications.
    """

    schedules = db.query(TeamSchedule).filter(TeamSchedule.season == season).all()
    repaired: list[str] = []
    unresolved: list[str] = []
    created_games = created_schedules = moved_game_stats = moved_stats = 0

    for expected in _real_week_zero_rows(season):
        early_schedule = _find_early_schedule(schedules, expected=expected)
        if early_schedule is None or early_schedule.game_id is None:
            unresolved.append(f"{expected.team}: missing verified Week 0 schedule/game for {expected.opponent}")
            continue
        game = db.get(Game, early_schedule.game_id)
        if game is None or not (
            _same_team(expected.team, game.home_team) or _same_team(expected.team, game.away_team)
        ):
            unresolved.append(f"{expected.team}: Week 0 game identity does not match {expected.opponent}")
            continue

        next_row = _next_regular_row(season=season, team=expected.team)
        existing_next = _find_early_schedule(schedules, expected=next_row)
        incumbent_week_zero = next(
            (row for row in schedules if _same_team(row.team_name, expected.team) and row.week == 0 and row.id != early_schedule.id),
            None,
        )
        if incumbent_week_zero is not None and not incumbent_week_zero.is_bye:
            unresolved.append(f"{expected.team}: conflicting non-bye Week 0 schedule row")
            continue
        if existing_next is not None and existing_next.week != 1:
            unresolved.append(f"{expected.team}: {next_row.opponent} already occupies Week {existing_next.week}")
            continue
        if existing_next is None:
            incumbent_week_one = next(
                (row for row in schedules if _same_team(row.team_name, expected.team) and row.week == 1 and row.id != early_schedule.id),
                None,
            )
            if incumbent_week_one is not None:
                unresolved.append(f"{expected.team}: conflicting Week 1 schedule row")
                continue

        if not apply:
            repaired.append(expected.team)
            if existing_next is None:
                created_games += 1
                created_schedules += 1
            continue

        if incumbent_week_zero is not None:
            db.delete(incumbent_week_zero)
            schedules.remove(incumbent_week_zero)
        old_week = early_schedule.week
        early_schedule.week = 0
        game.week = 0
        expected_date, expected_kickoff = _calendar_date_and_kickoff(expected.kickoff_at)
        early_schedule.game_date = expected_date or early_schedule.game_date
        early_schedule.kickoff_at = expected_kickoff or early_schedule.kickoff_at
        early_schedule.date_confirmed = bool(early_schedule.kickoff_at)
        game_stats, compatibility_stats = _move_compatibility_stats_to_week_zero(
            db, game_id=game.id, season=season, old_week=old_week
        )
        moved_game_stats += game_stats
        moved_stats += compatibility_stats

        if existing_next is None:
            next_date, next_kickoff = _calendar_date_and_kickoff(next_row.kickoff_at)
            next_game = Game(
                external_id=_event_id(
                    season=season, week=1, team=next_row.team, opponent=str(next_row.opponent)
                ),
                season=season,
                week=1,
                season_type="regular",
                schedule_status="scheduled",
                start_date=next_kickoff,
                home_team=next_row.team if next_row.location != "away" else str(next_row.opponent),
                away_team=str(next_row.opponent) if next_row.location != "away" else next_row.team,
                neutral_site=next_row.location == "neutral",
            )
            db.add(next_game)
            db.flush()
            existing_next = TeamSchedule(
                team_name=next_row.team,
                season=season,
                week=1,
                game_id=next_game.id,
                opponent_name=next_row.opponent,
                location=next_row.location,
                is_bye=False,
                game_date=next_date,
                kickoff_at=next_kickoff,
                neutral_site=next_row.location == "neutral",
                conference_game=False,
                date_confirmed=next_kickoff is not None,
            )
            db.add(existing_next)
            schedules.append(existing_next)
            created_games += 1
            created_schedules += 1
        repaired.append(expected.team)

    if unresolved and apply:
        raise EarlyGameScheduleReconciliationError("; ".join(unresolved))
    return EarlyGameScheduleReconciliationReport(
        season=season,
        applied=apply,
        repaired_teams=tuple(repaired),
        created_next_games=created_games,
        created_next_schedules=created_schedules,
        moved_player_game_stats=moved_game_stats,
        moved_player_stats=moved_stats,
        unresolved=tuple(unresolved),
    )
