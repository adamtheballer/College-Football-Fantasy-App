from __future__ import annotations

from sqlalchemy.orm import Session

from api.app.models.league import League
from api.app.models.matchup import Matchup
from api.app.models.standing import Standing
from api.app.models.team import Team
from api.app.schemas.scoring import WeekFinalizeResponse, WeekFinalizeStandingRead
from api.app.services.scoring_service import score_league_week


def rebuild_standings_through_week(db: Session, league: League, season: int, through_week: int) -> list[Standing]:
    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.name.asc(), Team.id.asc()).all()
    stats = {
        team.id: {
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "points_for": 0.0,
            "points_against": 0.0,
        }
        for team in teams
    }
    matchups = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == season,
            Matchup.week <= through_week,
            Matchup.status == "final",
        )
        .order_by(Matchup.week.asc(), Matchup.id.asc())
        .all()
    )
    for matchup in matchups:
        home = stats.get(matchup.home_team_id)
        away = stats.get(matchup.away_team_id)
        if home is None or away is None:
            continue
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

    existing = (
        db.query(Standing)
        .filter(Standing.league_id == league.id, Standing.season == season, Standing.week == through_week)
        .all()
    )
    existing_by_team = {row.team_id: row for row in existing}
    out: list[Standing] = []
    for team in teams:
        row = existing_by_team.get(team.id)
        if not row:
            row = Standing(league_id=league.id, team_id=team.id, season=season, week=through_week)
        row.wins = int(stats[team.id]["wins"])
        row.losses = int(stats[team.id]["losses"])
        row.ties = int(stats[team.id]["ties"])
        row.points_for = round(float(stats[team.id]["points_for"]), 2)
        row.points_against = round(float(stats[team.id]["points_against"]), 2)
        db.add(row)
        out.append(row)
    db.flush()
    return sorted(out, key=lambda row: (-row.wins, -float(row.points_for or 0.0), row.losses, next((t.name for t in teams if t.id == row.team_id), "")))


def get_standings(db: Session, league: League, season: int, week: int | None = None) -> list[Standing]:
    selected_week = week
    if selected_week is None:
        selected_week = (
            db.query(Standing.week)
            .filter(Standing.league_id == league.id, Standing.season == season)
            .order_by(Standing.week.desc())
            .limit(1)
            .scalar()
        )
    if selected_week is None:
        return []
    return rebuild_standings_through_week(db, league, season, selected_week)


def finalize_league_week(db: Session, league: League, season: int, week: int) -> WeekFinalizeResponse:
    score_league_week(db, league, season, week)
    matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league.id, Matchup.season == season, Matchup.week == week)
        .order_by(Matchup.id.asc())
        .all()
    )
    for matchup in matchups:
        matchup.status = "final"
        db.add(matchup)
    db.flush()
    standings = rebuild_standings_through_week(db, league, season, week)
    db.commit()
    team_ids = {row.team_id for row in standings}
    teams = db.query(Team).filter(Team.id.in_(team_ids)).all() if team_ids else []
    names = {team.id: team.name for team in teams}
    return WeekFinalizeResponse(
        league_id=league.id,
        season=season,
        week=week,
        finalized_matchups=len(matchups),
        standings=[
            WeekFinalizeStandingRead(
                team_id=row.team_id,
                team_name=names.get(row.team_id),
                wins=row.wins,
                losses=row.losses,
                ties=row.ties,
                points_for=float(row.points_for or 0.0),
                points_against=float(row.points_against or 0.0),
            )
            for row in standings
        ],
    )
