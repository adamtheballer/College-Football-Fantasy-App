from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from api.app.models.fantasy_player_score import FantasyPlayerScore
from api.app.models.league import League
from api.app.models.league_settings import LeagueSettings
from api.app.models.lineup import Lineup, LineupEntry
from api.app.models.matchup import Matchup
from api.app.models.player import Player
from api.app.models.player_stat import PlayerStat
from api.app.models.team import Team
from api.app.models.team_weekly_score import TeamWeeklyScore
from api.app.schemas.scoring import MatchupScoreRead, TeamWeeklyScoreRead, WeekScoreResponse


DEFAULT_SCORING: dict[str, float] = {
    "passing_yards": 0.04,
    "passing_touchdowns": 4.0,
    "interceptions": -2.0,
    "rushing_yards": 0.1,
    "rushing_touchdowns": 6.0,
    "receiving_yards": 0.1,
    "receiving_touchdowns": 6.0,
    "receptions": 1.0,
    "fumbles_lost": -2.0,
    "field_goals_made": 3.0,
    "extra_points_made": 1.0,
}

STAT_ALIASES: dict[str, tuple[str, ...]] = {
    "passing_yards": ("passing_yards", "PassingYards", "pass_yds", "PassYards"),
    "passing_touchdowns": ("passing_touchdowns", "PassingTouchdowns", "passing_tds", "pass_tds"),
    "interceptions": ("interceptions", "PassingInterceptions", "passing_interceptions"),
    "rushing_yards": ("rushing_yards", "RushingYards", "rush_yds"),
    "rushing_touchdowns": ("rushing_touchdowns", "RushingTouchdowns", "rushing_tds", "rush_tds"),
    "receiving_yards": ("receiving_yards", "ReceivingYards", "rec_yds"),
    "receiving_touchdowns": ("receiving_touchdowns", "ReceivingTouchdowns", "receiving_tds", "rec_tds"),
    "receptions": ("receptions", "Receptions"),
    "fumbles_lost": ("fumbles_lost", "FumblesLost"),
    "field_goals_made": ("field_goals_made", "FieldGoalsMade", "FieldGoals"),
    "extra_points_made": ("extra_points_made", "ExtraPointsMade"),
}


def number_from_stats(stats: dict[str, Any], key: str) -> float:
    for alias in STAT_ALIASES.get(key, (key,)):
        raw = stats.get(alias)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _league_scoring(db: Session, league: League) -> dict[str, float]:
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    raw = settings.scoring_json if settings and isinstance(settings.scoring_json, dict) else {}
    scoring = dict(DEFAULT_SCORING)
    aliases = {
        "ppr": "receptions",
        "passing_td": "passing_touchdowns",
        "passing_tds": "passing_touchdowns",
        "pass_td": "passing_touchdowns",
        "int": "interceptions",
        "rush_yd": "rushing_yards",
        "rec_yd": "receiving_yards",
        "fg": "field_goals_made",
        "xp": "extra_points_made",
    }
    for key, value in raw.items():
        target = aliases.get(str(key), str(key))
        if target not in scoring:
            continue
        try:
            scoring[target] = float(value)
        except (TypeError, ValueError):
            continue
    return scoring


def calculate_player_fantasy_points(stats: dict[str, Any], scoring_json: dict[str, float]) -> tuple[float, dict]:
    total = 0.0
    breakdown: dict[str, dict[str, float]] = {}
    for key, default_multiplier in DEFAULT_SCORING.items():
        value = number_from_stats(stats, key)
        multiplier = float(scoring_json.get(key, default_multiplier))
        points = value * multiplier
        total += points
        breakdown[key] = {
            "stat": value,
            "multiplier": multiplier,
            "points": round(points, 2),
        }
    return round(total, 2), breakdown


def score_league_week_players(db: Session, league: League, season: int, week: int) -> list[FantasyPlayerScore]:
    scoring = _league_scoring(db, league)
    stat_rows = (
        db.query(PlayerStat)
        .filter(PlayerStat.season == season, PlayerStat.week == week)
        .order_by(PlayerStat.player_id.asc())
        .all()
    )
    existing_rows = (
        db.query(FantasyPlayerScore)
        .filter(FantasyPlayerScore.league_id == league.id, FantasyPlayerScore.season == season, FantasyPlayerScore.week == week)
        .all()
    )
    existing_by_player = {row.player_id: row for row in existing_rows}
    out: list[FantasyPlayerScore] = []
    for stat_row in stat_rows:
        stats = stat_row.stats if isinstance(stat_row.stats, dict) else {}
        points, breakdown = calculate_player_fantasy_points(stats, scoring)
        score_row = existing_by_player.get(stat_row.player_id)
        if not score_row:
            score_row = FantasyPlayerScore(
                league_id=league.id,
                player_id=stat_row.player_id,
                season=season,
                week=week,
                source="computed",
            )
        score_row.points = points
        score_row.breakdown_json = breakdown
        db.add(score_row)
        out.append(score_row)
    db.flush()
    return out


def _lineup_for_team(db: Session, league: League, team: Team, season: int, week: int) -> Lineup | None:
    from api.app.services.lineup_service import get_or_create_lineup

    return get_or_create_lineup(db, league, team, season, week)


def score_team_week(db: Session, league: League, team: Team, season: int, week: int) -> TeamWeeklyScore:
    lineup = _lineup_for_team(db, league, team, season, week)
    entries = db.query(LineupEntry).filter(LineupEntry.lineup_id == lineup.id).all() if lineup else []
    player_ids = {entry.player_id for entry in entries}
    player_scores = (
        db.query(FantasyPlayerScore)
        .filter(
            FantasyPlayerScore.league_id == league.id,
            FantasyPlayerScore.season == season,
            FantasyPlayerScore.week == week,
            FantasyPlayerScore.player_id.in_(player_ids),
        )
        .all()
        if player_ids
        else []
    )
    points_by_player = {row.player_id: float(row.points or 0.0) for row in player_scores}
    starter_points = 0.0
    bench_points = 0.0
    entry_breakdown: list[dict[str, Any]] = []
    for entry in entries:
        points = points_by_player.get(entry.player_id, 0.0)
        if entry.is_starter:
            starter_points += points
        else:
            bench_points += points
        entry_breakdown.append(
            {"player_id": entry.player_id, "slot": entry.slot, "is_starter": bool(entry.is_starter), "points": points}
        )

    score_row = (
        db.query(TeamWeeklyScore)
        .filter(
            TeamWeeklyScore.league_id == league.id,
            TeamWeeklyScore.team_id == team.id,
            TeamWeeklyScore.season == season,
            TeamWeeklyScore.week == week,
        )
        .first()
    )
    if not score_row:
        score_row = TeamWeeklyScore(league_id=league.id, team_id=team.id, season=season, week=week)
    score_row.lineup_id = lineup.id if lineup else None
    score_row.starter_points = round(starter_points, 2)
    score_row.bench_points = round(bench_points, 2)
    score_row.total_points = round(starter_points + bench_points, 2)
    score_row.breakdown_json = {"entries": entry_breakdown}
    db.add(score_row)
    db.flush()
    return score_row


def score_league_week_teams(db: Session, league: League, season: int, week: int) -> list[TeamWeeklyScore]:
    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.id.asc()).all()
    return [score_team_week(db, league, team, season, week) for team in teams]


def update_matchup_scores_for_week(db: Session, league: League, season: int, week: int) -> list[Matchup]:
    team_scores = (
        db.query(TeamWeeklyScore)
        .filter(TeamWeeklyScore.league_id == league.id, TeamWeeklyScore.season == season, TeamWeeklyScore.week == week)
        .all()
    )
    starter_points = {row.team_id: float(row.starter_points or 0.0) for row in team_scores}
    matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league.id, Matchup.season == season, Matchup.week == week)
        .order_by(Matchup.id.asc())
        .all()
    )
    for matchup in matchups:
        matchup.home_score = round(starter_points.get(matchup.home_team_id, 0.0), 2)
        matchup.away_score = round(starter_points.get(matchup.away_team_id, 0.0), 2)
        if matchup.status != "final":
            matchup.status = "projected"
        db.add(matchup)
    db.flush()
    return matchups


def serialize_team_scores(db: Session, rows: list[TeamWeeklyScore]) -> list[TeamWeeklyScoreRead]:
    team_ids = {row.team_id for row in rows}
    teams = db.query(Team).filter(Team.id.in_(team_ids)).all() if team_ids else []
    names = {team.id: team.name for team in teams}
    return [
        TeamWeeklyScoreRead(
            team_id=row.team_id,
            team_name=names.get(row.team_id),
            season=row.season,
            week=row.week,
            starter_points=float(row.starter_points or 0.0),
            bench_points=float(row.bench_points or 0.0),
            total_points=float(row.total_points or 0.0),
            breakdown_json=row.breakdown_json or {},
        )
        for row in rows
    ]


def serialize_matchups(db: Session, rows: list[Matchup]) -> list[MatchupScoreRead]:
    team_ids = {row.home_team_id for row in rows} | {row.away_team_id for row in rows}
    teams = db.query(Team).filter(Team.id.in_(team_ids)).all() if team_ids else []
    names = {team.id: team.name for team in teams}
    return [
        MatchupScoreRead(
            matchup_id=row.id,
            week=row.week,
            status=row.status,
            home_team_id=row.home_team_id,
            home_team_name=names.get(row.home_team_id),
            home_score=float(row.home_score or 0.0),
            away_team_id=row.away_team_id,
            away_team_name=names.get(row.away_team_id),
            away_score=float(row.away_score or 0.0),
        )
        for row in rows
    ]


def score_league_week(db: Session, league: League, season: int, week: int) -> WeekScoreResponse:
    player_scores = score_league_week_players(db, league, season, week)
    team_scores = score_league_week_teams(db, league, season, week)
    matchups = update_matchup_scores_for_week(db, league, season, week)
    db.commit()
    return WeekScoreResponse(
        league_id=league.id,
        season=season,
        week=week,
        player_scores_count=len(player_scores),
        team_scores=serialize_team_scores(db, team_scores),
        matchups=serialize_matchups(db, matchups),
    )
