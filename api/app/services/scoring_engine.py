from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.scoring import (
    build_rules_bundle_from_league_scoring_json,
    calculate_fantasy_points,
)

ScoringSourceMode = Literal["actual_then_projection", "projection_only", "actual_only"]


@dataclass
class TeamWeekScoreResult:
    team_id: int
    team_name: str
    starters_points: float
    bench_points: float
    total_points: float


@dataclass
class MatchupScoreResult:
    matchup_id: int
    home_team_id: int
    away_team_id: int
    home_score: float
    away_score: float
    status: str


@dataclass
class WeekScoringResult:
    team_scores: list[TeamWeekScoreResult]
    matchup_scores: list[MatchupScoreResult]
    player_actual_points_used: int
    player_projection_points_used: int


def _starter_slot(slot: str | None) -> bool:
    if not slot:
        return True
    normalized = slot.strip().upper()
    return normalized not in {"BENCH", "IR", "BE"}


def _actual_points_map(
    db: Session,
    *,
    player_ids: set[int],
    season: int,
    week: int,
    rules_bundle: dict | None = None,
) -> dict[int, float]:
    if not player_ids:
        return {}
    rows = (
        db.query(PlayerStat, Player)
        .join(Player, Player.id == PlayerStat.player_id)
        .filter(
            PlayerStat.player_id.in_(player_ids),
            PlayerStat.season == season,
            PlayerStat.week == week,
        )
        .all()
    )
    out: dict[int, float] = {}
    for row, player in rows:
        stats = row.stats if isinstance(row.stats, dict) else {}
        out[player.id] = calculate_fantasy_points(stats, rules_bundle=rules_bundle, position=player.position)
    return out


def _projection_points_map(db: Session, *, player_ids: set[int], season: int, week: int) -> dict[int, float]:
    if not player_ids:
        return {}
    rows = (
        db.query(WeeklyProjection.player_id, WeeklyProjection.fantasy_points)
        .filter(
            WeeklyProjection.player_id.in_(player_ids),
            WeeklyProjection.season == season,
            WeeklyProjection.week == week,
        )
        .all()
    )
    return {int(player_id): float(points or 0.0) for player_id, points in rows}


def recompute_week_scores(
    db: Session,
    *,
    league_id: int,
    season: int,
    week: int,
    source_mode: ScoringSourceMode,
    finalize_matchups: bool,
) -> WeekScoringResult:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    scoring_json = settings_row.scoring_json if settings_row and isinstance(settings_row.scoring_json, dict) else {}
    league_rules_bundle = build_rules_bundle_from_league_scoring_json(scoring_json)

    teams = (
        db.query(Team)
        .filter(Team.league_id == league_id)
        .order_by(Team.id.asc())
        .all()
    )
    team_by_id = {row.id: row for row in teams}

    roster_rows = (
        db.query(RosterEntry)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league_id)
        .all()
    )
    player_ids = {int(row.player_id) for row in roster_rows}

    actual_points = _actual_points_map(
        db,
        player_ids=player_ids,
        season=season,
        week=week,
        rules_bundle=league_rules_bundle,
    )
    projection_points = _projection_points_map(db, player_ids=player_ids, season=season, week=week)

    player_actual_points_used = 0
    player_projection_points_used = 0

    existing_scores = (
        db.query(TeamWeekScore)
        .filter(
            TeamWeekScore.league_id == league_id,
            TeamWeekScore.season == season,
            TeamWeekScore.week == week,
        )
        .all()
    )
    existing_by_team = {row.team_id: row for row in existing_scores}

    starters_by_team: dict[int, float] = {team.id: 0.0 for team in teams}
    bench_by_team: dict[int, float] = {team.id: 0.0 for team in teams}

    for row in roster_rows:
        points_value = 0.0
        if source_mode == "actual_only":
            points_value = float(actual_points.get(row.player_id, 0.0))
            if row.player_id in actual_points:
                player_actual_points_used += 1
        elif source_mode == "projection_only":
            points_value = float(projection_points.get(row.player_id, 0.0))
            if row.player_id in projection_points:
                player_projection_points_used += 1
        else:
            if row.player_id in actual_points:
                points_value = float(actual_points[row.player_id])
                player_actual_points_used += 1
            else:
                points_value = float(projection_points.get(row.player_id, 0.0))
                if row.player_id in projection_points:
                    player_projection_points_used += 1

        if _starter_slot(row.slot):
            starters_by_team[row.team_id] = float(starters_by_team.get(row.team_id, 0.0) + points_value)
        else:
            bench_by_team[row.team_id] = float(bench_by_team.get(row.team_id, 0.0) + points_value)

    team_results: list[TeamWeekScoreResult] = []
    for team in teams:
        starters_points = round(float(starters_by_team.get(team.id, 0.0)), 2)
        bench_points = round(float(bench_by_team.get(team.id, 0.0)), 2)
        total_points = round(starters_points + bench_points, 2)

        row = existing_by_team.get(team.id)
        if not row:
            row = TeamWeekScore(
                league_id=league_id,
                team_id=team.id,
                season=season,
                week=week,
            )
        row.points_starters = starters_points
        row.points_bench = bench_points
        row.points_total = total_points
        db.add(row)

        team_results.append(
            TeamWeekScoreResult(
                team_id=team.id,
                team_name=team.name,
                starters_points=starters_points,
                bench_points=bench_points,
                total_points=total_points,
            )
        )

    db.flush()

    starters_lookup = {row.team_id: row.starters_points for row in team_results}
    matchup_rows = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league_id,
            Matchup.season == season,
            Matchup.week == week,
        )
        .all()
    )
    matchup_results: list[MatchupScoreResult] = []
    for matchup in matchup_rows:
        home_score = round(float(starters_lookup.get(matchup.home_team_id, 0.0)), 2)
        away_score = round(float(starters_lookup.get(matchup.away_team_id, 0.0)), 2)
        matchup.home_score = home_score
        matchup.away_score = away_score
        if finalize_matchups:
            matchup.status = "final"
        elif matchup.status != "final":
            matchup.status = "projected"
        db.add(matchup)
        matchup_results.append(
            MatchupScoreResult(
                matchup_id=matchup.id,
                home_team_id=matchup.home_team_id,
                away_team_id=matchup.away_team_id,
                home_score=home_score,
                away_score=away_score,
                status=matchup.status,
            )
        )

    db.flush()

    # Normalize order for stable API/testing behavior.
    team_results.sort(key=lambda row: row.team_id)
    matchup_results.sort(key=lambda row: row.matchup_id)

    return WeekScoringResult(
        team_scores=team_results,
        matchup_scores=matchup_results,
        player_actual_points_used=player_actual_points_used,
        player_projection_points_used=player_projection_points_used,
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
