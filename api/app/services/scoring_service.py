from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.scoring_engine import (
    calculate_player_fantasy_points,
    is_starting_slot,
    normalize_player_stats,
)
from collegefootballfantasy_api.app.domain.scoring_rules import NON_SCORING_SLOTS, normalize_scoring_rules
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore


FINAL_MATCHUP_STATUSES = {"final", "stat_corrected"}


@dataclass(frozen=True)
class ScoringSummary:
    players_scored: int
    teams_scored: int
    matchups_updated: int
    standings_updated: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _league_settings(db: Session, league_id: int) -> LeagueSettings | None:
    return db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()


def create_or_refresh_lineup_snapshots(db: Session, league_id: int, season: int, week: int) -> int:
    existing_player_ids = {
        player_id
        for (player_id,) in db.query(LineupWeekSnapshot.player_id)
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
        )
        .all()
    }
    roster_entries = (
        db.query(RosterEntry)
        .filter(RosterEntry.league_id == league_id)
        .order_by(RosterEntry.team_id.asc(), RosterEntry.id.asc())
        .all()
    )
    locked_at = _now()
    created = 0
    for entry in roster_entries:
        if entry.player_id in existing_player_ids:
            continue
        snapshot = LineupWeekSnapshot(
            league_id=league_id,
            team_id=entry.team_id,
            player_id=entry.player_id,
            season=season,
            week=week,
            slot=(entry.slot or "BENCH").upper(),
            is_starter=is_starting_slot(entry.slot or ""),
            locked_at=locked_at,
        )
        db.add(snapshot)
        created += 1
    if created:
        db.flush()
    return created


def _stat_map(db: Session, season: int, week: int, player_ids: set[int]) -> dict[int, PlayerStat]:
    if not player_ids:
        return {}
    rows = (
        db.query(PlayerStat)
        .filter(
            PlayerStat.season == season,
            PlayerStat.week == week,
            PlayerStat.player_id.in_(player_ids),
        )
        .all()
    )
    return {row.player_id: row for row in rows}


def recalculate_player_week_scores(db: Session, league_id: int, season: int, week: int) -> int:
    settings = _league_settings(db, league_id)
    scoring_rules = settings.scoring_json if settings else {}
    players = db.query(Player).order_by(Player.id.asc()).all()
    player_ids = {player.id for player in players}
    stat_by_player = _stat_map(db, season, week, player_ids)
    calculated_at = _now()
    scored = 0
    for player in players:
        stat_row = stat_by_player.get(player.id)
        normalized_stats = normalize_player_stats(stat_row.stats if stat_row else {}, player.position)
        fantasy_points, breakdown = calculate_player_fantasy_points(normalized_stats, scoring_rules, player.position)
        score = (
            db.query(PlayerWeekScore)
            .filter(
                PlayerWeekScore.league_id == league_id,
                PlayerWeekScore.player_id == player.id,
                PlayerWeekScore.season == season,
                PlayerWeekScore.week == week,
            )
            .first()
        )
        if not score:
            score = PlayerWeekScore(
                league_id=league_id,
                player_id=player.id,
                season=season,
                week=week,
            )
            db.add(score)
        score.fantasy_points = fantasy_points
        score.breakdown_json = breakdown
        score.source_stat_id = stat_row.id if stat_row else None
        score.calculated_at = calculated_at
        scored += 1
    if scored:
        db.flush()
    return scored


def recalculate_team_week_score(db: Session, league_id: int, team_id: int, season: int, week: int) -> TeamWeekScore:
    snapshots = (
        db.query(LineupWeekSnapshot)
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.team_id == team_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
        )
        .all()
    )
    score_by_player = {
        row.player_id: row
        for row in db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
            PlayerWeekScore.player_id.in_({snapshot.player_id for snapshot in snapshots} or {0}),
        )
        .all()
    }
    starter_points = 0.0
    bench_points = 0.0
    player_breakdown = []
    for snapshot in snapshots:
        score = score_by_player.get(snapshot.player_id)
        points = float(score.fantasy_points if score else 0.0)
        slot = (snapshot.slot or "").upper()
        if snapshot.is_starter:
            starter_points += points
        elif slot not in NON_SCORING_SLOTS:
            bench_points += points
        player_breakdown.append(
            {
                "player_id": snapshot.player_id,
                "slot": slot,
                "is_starter": snapshot.is_starter,
                "points": round(points, 2),
            }
        )
    team_score = (
        db.query(TeamWeekScore)
        .filter(
            TeamWeekScore.league_id == league_id,
            TeamWeekScore.team_id == team_id,
            TeamWeekScore.season == season,
            TeamWeekScore.week == week,
        )
        .first()
    )
    if not team_score:
        team_score = TeamWeekScore(
            league_id=league_id,
            team_id=team_id,
            season=season,
            week=week,
        )
        db.add(team_score)
    team_score.starter_points = round(starter_points, 2)
    team_score.bench_points = round(bench_points, 2)
    team_score.total_points = round(starter_points, 2)
    team_score.points_starters = team_score.starter_points
    team_score.points_bench = team_score.bench_points
    team_score.points_total = team_score.total_points
    team_score.breakdown_json = {
        "players": player_breakdown,
        "starter_points": team_score.starter_points,
        "bench_points": team_score.bench_points,
        "total_points": team_score.total_points,
    }
    team_score.status = "live"
    team_score.calculated_at = _now()
    db.flush()
    return team_score


def recalculate_team_week_scores(db: Session, league_id: int, season: int, week: int) -> int:
    team_ids = [
        team_id
        for (team_id,) in db.query(Team.id)
        .filter(Team.league_id == league_id)
        .order_by(Team.id.asc())
        .all()
    ]
    for team_id in team_ids:
        recalculate_team_week_score(db, league_id, team_id, season, week)
    return len(team_ids)


def _team_score_map(db: Session, league_id: int, season: int, week: int) -> dict[int, TeamWeekScore]:
    rows = (
        db.query(TeamWeekScore)
        .filter(
            TeamWeekScore.league_id == league_id,
            TeamWeekScore.season == season,
            TeamWeekScore.week == week,
        )
        .all()
    )
    return {row.team_id: row for row in rows}


def recalculate_matchup_scores(db: Session, league_id: int, season: int, week: int) -> int:
    score_by_team = _team_score_map(db, league_id, season, week)
    matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week == week)
        .all()
    )
    updated = 0
    for matchup in matchups:
        home_score = score_by_team.get(matchup.home_team_id)
        away_score = score_by_team.get(matchup.away_team_id)
        matchup.home_score = float(home_score.total_points if home_score else 0.0)
        matchup.away_score = float(away_score.total_points if away_score else 0.0)
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            matchup.status = "live"
        updated += 1
    if updated:
        db.flush()
    return updated


def _upsert_standing(
    db: Session,
    league_id: int,
    team_id: int,
    season: int,
    week: int,
    wins: int,
    losses: int,
    ties: int,
    points_for: float,
    points_against: float,
) -> Standing:
    standing = (
        db.query(Standing)
        .filter(
            Standing.league_id == league_id,
            Standing.team_id == team_id,
            Standing.season == season,
            Standing.week == week,
        )
        .first()
    )
    if not standing:
        standing = Standing(league_id=league_id, team_id=team_id, season=season, week=week)
        db.add(standing)
    standing.wins = wins
    standing.losses = losses
    standing.ties = ties
    standing.points_for = round(points_for, 2)
    standing.points_against = round(points_against, 2)
    return standing


def recalculate_standings_for_week(db: Session, league_id: int, season: int, week: int) -> int:
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    records = {
        team.id: {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0}
        for team in teams
    }
    final_matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week <= week)
        .all()
    )
    for matchup in final_matchups:
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            continue
        home = records.setdefault(matchup.home_team_id, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0})
        away = records.setdefault(matchup.away_team_id, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0})
        home_score = float(matchup.home_score or 0.0)
        away_score = float(matchup.away_score or 0.0)
        home["points_for"] += home_score
        home["points_against"] += away_score
        away["points_for"] += away_score
        away["points_against"] += home_score
        if home_score > away_score:
            home["wins"] += 1
            away["losses"] += 1
        elif away_score > home_score:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["ties"] += 1
            away["ties"] += 1
    for team_id, record in records.items():
        _upsert_standing(
            db,
            league_id,
            team_id,
            season,
            week,
            int(record["wins"]),
            int(record["losses"]),
            int(record["ties"]),
            float(record["points_for"]),
            float(record["points_against"]),
        )
    if records:
        db.flush()
    return len(records)


def recalculate_league_week_scores(db: Session, league_id: int, season: int, week: int) -> ScoringSummary:
    create_or_refresh_lineup_snapshots(db, league_id, season, week)
    players_scored = recalculate_player_week_scores(db, league_id, season, week)
    teams_scored = recalculate_team_week_scores(db, league_id, season, week)
    matchups_updated = recalculate_matchup_scores(db, league_id, season, week)
    standings_updated = recalculate_standings_for_week(db, league_id, season, week)
    return ScoringSummary(
        players_scored=players_scored,
        teams_scored=teams_scored,
        matchups_updated=matchups_updated,
        standings_updated=standings_updated,
    )


def run_league_scoring_recalculation(
    db: Session,
    league_id: int | None,
    season: int,
    week: int,
    provider: str = "manual",
) -> ScoringSummary:
    run = ScoringRun(
        league_id=league_id,
        season=season,
        week=week,
        provider=provider,
        status="running",
        started_at=_now(),
    )
    db.add(run)
    db.flush()
    try:
        if league_id is not None:
            if not db.get(League, league_id):
                raise ValueError(f"league {league_id} not found")
            summary = recalculate_league_week_scores(db, league_id, season, week)
        else:
            summary = ScoringSummary(0, 0, 0, 0)
            leagues = db.query(League).filter(League.season_year == season).all()
            for league in leagues:
                current = recalculate_league_week_scores(db, league.id, season, week)
                summary = ScoringSummary(
                    players_scored=summary.players_scored + current.players_scored,
                    teams_scored=summary.teams_scored + current.teams_scored,
                    matchups_updated=summary.matchups_updated + current.matchups_updated,
                    standings_updated=summary.standings_updated + current.standings_updated,
                )
        run.status = "success"
        run.completed_at = _now()
        run.players_updated = summary.players_scored
        run.teams_updated = summary.teams_scored
        run.matchups_updated = summary.matchups_updated
        db.commit()
        return summary
    except Exception as exc:
        run.status = "failed"
        run.completed_at = _now()
        run.error_message = str(exc)[:1000]
        db.commit()
        raise
