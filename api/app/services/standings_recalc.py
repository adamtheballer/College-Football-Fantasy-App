from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.matchup_state import FINAL_MATCHUP_STATUSES
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team


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
        .order_by(Matchup.week.asc(), Matchup.id.asc())
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
