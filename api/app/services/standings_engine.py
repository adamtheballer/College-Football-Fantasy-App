from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team


def build_standings_snapshot(
    db: Session,
    *,
    league_id: int,
    season: int,
    through_week: int,
) -> list[Standing]:
    teams = (
        db.query(Team)
        .filter(Team.league_id == league_id)
        .order_by(Team.id.asc())
        .all()
    )
    if not teams:
        return []

    stats: dict[int, dict[str, float | int]] = {
        team.id: {
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "points_for": 0.0,
            "points_against": 0.0,
        }
        for team in teams
    }

    matchup_rows = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league_id,
            Matchup.season == season,
            Matchup.week <= through_week,
        )
        .order_by(Matchup.week.asc(), Matchup.id.asc())
        .all()
    )

    for matchup in matchup_rows:
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

        if matchup.status != "final":
            continue

        if home_score > away_score:
            home["wins"] += 1
            away["losses"] += 1
        elif home_score < away_score:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["ties"] += 1
            away["ties"] += 1

    existing_rows = (
        db.query(Standing)
        .filter(
            Standing.league_id == league_id,
            Standing.season == season,
            Standing.week == through_week,
        )
        .all()
    )
    existing_by_team_id = {row.team_id: row for row in existing_rows}

    out_rows: list[Standing] = []
    for team in teams:
        team_stats = stats[team.id]
        row = existing_by_team_id.get(team.id)
        if not row:
            row = Standing(
                league_id=league_id,
                team_id=team.id,
                season=season,
                week=through_week,
            )
        row.wins = int(team_stats["wins"])
        row.losses = int(team_stats["losses"])
        row.ties = int(team_stats["ties"])
        row.points_for = float(team_stats["points_for"])
        row.points_against = float(team_stats["points_against"])
        db.add(row)
        out_rows.append(row)

    db.flush()
    return sorted(out_rows, key=lambda row: (row.wins, row.points_for), reverse=True)
