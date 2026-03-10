from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.schemas.schedule import SchedulePreviewList, SchedulePreview
from collegefootballfantasy_api.app.services.matchup_grades import build_matchup_row

router = APIRouter()


@router.get("/player/{player_id}", response_model=SchedulePreviewList)
def schedule_preview(
    player_id: int,
    season: int,
    week: int,
    weeks: int = 4,
    db: Session = Depends(get_db),
) -> SchedulePreviewList:
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    games = (
        db.query(Game)
        .filter(Game.season == season, Game.week >= week)
        .filter(or_(Game.home_team == player.school, Game.away_team == player.school))
        .order_by(Game.week.asc())
        .limit(weeks)
        .all()
    )

    data: list[SchedulePreview] = []
    for game in games:
        opponent = game.away_team if game.home_team == player.school else game.home_team
        home_away = "home" if game.home_team == player.school else "away"
        defense = (
            db.query(DefenseRating)
            .filter(DefenseRating.team_name == opponent, DefenseRating.season == season, DefenseRating.week == game.week)
            .first()
        )
        matchup = build_matchup_row(opponent, season, game.week, player.position, defense, None)
        data.append(
            SchedulePreview(
                week=game.week,
                opponent=opponent,
                home_away=home_away,
                grade=matchup["grade"],
            )
        )

    return SchedulePreviewList(data=data)
