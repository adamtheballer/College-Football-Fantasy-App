from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.schemas.player import PlayerCreate


def create_players(db: Session, players_in: list[PlayerCreate]) -> list[Player]:
    players = [Player(**player.model_dump()) for player in players_in]
    db.add_all(players)
    db.commit()
    for player in players:
        db.refresh(player)
    return players


def list_players(
    db: Session,
    limit: int,
    offset: int,
    position: str | None,
    school: str | None,
    search: str | None,
    league_id: int | None = None,
    available_only: bool = False,
    sort: str | None = None,
) -> tuple[list[Player], int]:
    stmt: Select = select(Player)
    if position:
        stmt = stmt.where(Player.position == position)
    if school:
        stmt = stmt.where(Player.school == school)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Player.name.ilike(pattern) | Player.school.ilike(pattern))
    if league_id is not None and available_only:
        unavailable_players = (
            select(RosterEntry.player_id)
            .join(Team, Team.id == RosterEntry.team_id)
            .where(Team.league_id == league_id)
        )
        stmt = stmt.where(Player.id.not_in(unavailable_players))

    if sort == "school":
        stmt = stmt.order_by(Player.school.asc(), Player.name.asc())
    elif sort == "position":
        stmt = stmt.order_by(Player.position.asc(), Player.name.asc())
    else:
        stmt = stmt.order_by(Player.name.asc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt)
    players = db.scalars(stmt.offset(offset).limit(limit)).all()
    return players, total or 0


def get_player(db: Session, player_id: int) -> Player | None:
    return db.get(Player, player_id)
