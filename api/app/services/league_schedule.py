from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.team import Team


def generate_round_robin_weeks(team_ids: list[int], weeks: int) -> list[list[tuple[int, int]]]:
    if len(team_ids) < 2:
        return []
    if len(team_ids) % 2 != 0:
        raise ValueError("Even number of teams required for every team to play each week.")

    teams = list(team_ids)
    rounds_per_cycle = len(teams) - 1
    weeks_out: list[list[tuple[int, int]]] = []

    for week_index in range(weeks):
        rotated = list(teams)
        for _ in range(week_index % rounds_per_cycle):
            movable = rotated.pop()
            rotated.insert(1, movable)

        week_matchups: list[tuple[int, int]] = []
        for index in range(len(rotated) // 2):
            left = rotated[index]
            right = rotated[len(rotated) - 1 - index]
            week_matchups.append((left, right) if week_index % 2 == 0 else (right, left))
        weeks_out.append(week_matchups)

    return weeks_out


def ensure_league_schedule(
    db: Session,
    league: League,
    regular_season_weeks: int = 12,
) -> int:
    existing_count = (
        db.query(Matchup)
        .filter(Matchup.league_id == league.id, Matchup.season == league.season_year)
        .count()
    )
    if existing_count > 0:
        return existing_count

    teams = (
        db.query(Team)
        .filter(Team.league_id == league.id)
        .order_by(Team.created_at.asc(), Team.id.asc())
        .all()
    )
    if len(teams) < 2 or len(teams) % 2 != 0:
        return 0

    created = 0
    for week_index, week_matchups in enumerate(
        generate_round_robin_weeks([team.id for team in teams], regular_season_weeks),
        start=1,
    ):
        for home_team_id, away_team_id in week_matchups:
            exists = (
                db.query(Matchup)
                .filter(
                    Matchup.league_id == league.id,
                    Matchup.season == league.season_year,
                    Matchup.week == week_index,
                    Matchup.home_team_id == home_team_id,
                    Matchup.away_team_id == away_team_id,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                Matchup(
                    league_id=league.id,
                    season=league.season_year,
                    week=week_index,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    status="projected",
                    home_score=0.0,
                    away_score=0.0,
                )
            )
            created += 1
    return created
