from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.defense_vs_position import DefenseVsPosition
from collegefootballfantasy_api.app.schemas.matchup import MatchupGradeList, MatchupGradeRead
from collegefootballfantasy_api.app.services.matchup_grades import build_matchup_row

router = APIRouter()


@router.get("", response_model=MatchupGradeList)
def list_matchups(
    season: int,
    week: int,
    team: str | None = None,
    position: str | None = None,
    db: Session = Depends(get_db),
) -> MatchupGradeList:
    if team and position:
        defense = (
            db.query(DefenseRating)
            .filter(DefenseRating.team_name == team, DefenseRating.season == season, DefenseRating.week == week)
            .first()
        )
        cached = (
            db.query(DefenseVsPosition)
            .filter(
                DefenseVsPosition.team_name == team,
                DefenseVsPosition.season == season,
                DefenseVsPosition.week == week,
                DefenseVsPosition.position == position.upper(),
            )
            .first()
        )
        row = build_matchup_row(team, season, week, position.upper(), defense, cached)
        data = [MatchupGradeRead(**row)]
        return MatchupGradeList(data=data, total=len(data))

    cached_query = db.query(DefenseVsPosition).filter(
        DefenseVsPosition.season == season, DefenseVsPosition.week == week
    )
    if team:
        cached_query = cached_query.filter(DefenseVsPosition.team_name == team)
    if position:
        cached_query = cached_query.filter(DefenseVsPosition.position == position.upper())
    cached_rows = cached_query.all()

    if cached_rows:
        data = [
            MatchupGradeRead(
                team=row.team_name,
                season=row.season,
                week=row.week,
                position=row.position,
                grade=row.grade,
                rank=row.rank,
                yards_per_target=row.yards_per_target,
                yards_per_rush=row.yards_per_rush,
                pass_td_rate=row.pass_td_rate,
                rush_td_rate=row.rush_td_rate,
                explosive_rate=row.explosive_rate,
                pressure_rate=row.pressure_rate,
            )
            for row in cached_rows
        ]
        return MatchupGradeList(data=data, total=len(data))

    defense_rows = db.query(DefenseRating).filter(
        DefenseRating.season == season, DefenseRating.week == week
    ).all()
    data = []
    for defense in defense_rows:
        for pos in ["QB", "RB", "WR", "TE"]:
            row = build_matchup_row(defense.team_name, season, week, pos, defense, None)
            data.append(MatchupGradeRead(**row))
    return MatchupGradeList(data=data, total=len(data))
