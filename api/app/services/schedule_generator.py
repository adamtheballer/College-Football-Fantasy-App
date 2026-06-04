from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.app.models.league import League
from api.app.models.matchup import Matchup
from api.app.models.team import Team
from api.app.schemas.scoring import MatchupScoreRead


def get_league_teams(db: Session, league: League) -> list[Team]:
    return (
        db.query(Team)
        .filter(Team.league_id == league.id)
        .order_by(Team.created_at.asc(), Team.id.asc())
        .all()
    )


def schedule_exists(db: Session, league: League) -> bool:
    return db.query(Matchup.id).filter(Matchup.league_id == league.id).first() is not None


def _round_robin_rounds(teams: list[Team]) -> list[list[tuple[Team | None, Team | None]]]:
    entries: list[Team | None] = list(teams)
    if len(entries) % 2 == 1:
        entries.append(None)
    rounds: list[list[tuple[Team | None, Team | None]]] = []
    team_count = len(entries)
    for round_index in range(team_count - 1):
        pairings: list[tuple[Team | None, Team | None]] = []
        for index in range(team_count // 2):
            left = entries[index]
            right = entries[team_count - 1 - index]
            if round_index % 2 == 0:
                pairings.append((left, right))
            else:
                pairings.append((right, left))
        rounds.append(pairings)
        entries = [entries[0], entries[-1], *entries[1:-1]]
    return rounds


def generate_league_schedule(db: Session, league: League, weeks: int = 12) -> list[Matchup]:
    if weeks < 1 or weeks > 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="weeks must be between 1 and 20")
    teams = get_league_teams(db, league)
    if len(teams) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="at least two teams are required")
    if schedule_exists(db, league):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="schedule already exists")

    rounds = _round_robin_rounds(teams)
    matchups: list[Matchup] = []
    for week in range(1, weeks + 1):
        round_pairings = rounds[(week - 1) % len(rounds)]
        for home, away in round_pairings:
            if home is None or away is None:
                continue
            matchup = Matchup(
                league_id=league.id,
                season=league.season_year,
                week=week,
                home_team_id=home.id,
                away_team_id=away.id,
                status="scheduled",
                home_score=0.0,
                away_score=0.0,
            )
            db.add(matchup)
            matchups.append(matchup)
    db.commit()
    for matchup in matchups:
        db.refresh(matchup)
    return matchups


def get_league_schedule(db: Session, league: League) -> list[Matchup]:
    return (
        db.query(Matchup)
        .filter(Matchup.league_id == league.id, Matchup.season == league.season_year)
        .order_by(Matchup.week.asc(), Matchup.id.asc())
        .all()
    )


def serialize_matchups(db: Session, matchups: list[Matchup]) -> list[MatchupScoreRead]:
    team_ids = {row.home_team_id for row in matchups} | {row.away_team_id for row in matchups}
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
        for row in matchups
    ]
