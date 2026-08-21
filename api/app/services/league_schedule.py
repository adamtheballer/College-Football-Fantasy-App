from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.team import Team


# Retained as a compatibility fallback for callers that explicitly select a
# duration. New league schedules derive the approved season calendar and
# reserve the correct number of postseason weeks.
REGULAR_SEASON_WEEKS = 13


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
    regular_season_weeks: int | None = None,
) -> int:
    # A draft finalization can stage matchups and invoke this again before the
    # transaction commits. Flush first so schedule generation stays idempotent.
    db.flush()
    if regular_season_weeks is None:
        from collegefootballfantasy_api.app.services.postseason_service import get_or_create_postseason_settings

        regular_season_weeks = get_or_create_postseason_settings(db, league).regular_season_end_week
    teams = (
        db.query(Team)
        .filter(Team.league_id == league.id)
        .order_by(Team.created_at.asc(), Team.id.asc())
        .all()
    )
    if len(teams) < 2:
        return 0
    if len(teams) % 2 != 0:
        raise ValueError("Even number of teams required for every team to play each week.")

    existing_matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league.id, Matchup.season == league.season_year)
        .all()
    )
    matchups_per_week = len(teams) // 2
    existing_by_week: dict[int, list[Matchup]] = {}
    for matchup in existing_matchups:
        existing_by_week.setdefault(matchup.week, []).append(matchup)

    # Never silently delete or repurpose an old regular-season row. A legacy
    # schedule extending into newly reserved playoff weeks needs an explicit
    # readiness review before a bracket can safely materialize there.
    reserved_rows = [
        matchup
        for week, matchups in existing_by_week.items()
        if week > regular_season_weeks
        for matchup in matchups
        if (matchup.status or "").lower() not in {"final", "completed", "stat_corrected"}
    ]
    if reserved_rows:
        raise ValueError(
            "existing future matchups occupy reserved postseason week(s): "
            + ", ".join(str(row.week) for row in sorted(reserved_rows, key=lambda row: (row.week, row.id)))
        )

    invalid_weeks = [
        week
        for week, matchups in existing_by_week.items()
        if week <= regular_season_weeks and len(matchups) not in {0, matchups_per_week}
    ]
    if invalid_weeks:
        raise ValueError(
            "Existing league schedule is incomplete for week(s): "
            + ", ".join(str(week) for week in sorted(invalid_weeks))
        )

    created = 0
    for week_index, week_matchups in enumerate(
        generate_round_robin_weeks([team.id for team in teams], regular_season_weeks),
        start=1,
    ):
        if existing_by_week.get(week_index):
            continue
        for home_team_id, away_team_id in week_matchups:
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
