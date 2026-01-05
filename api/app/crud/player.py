from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
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
) -> tuple[list[Player], int]:
    stmt: Select = select(Player)
    if position:
        stmt = stmt.where(Player.position == position)
    if school:
        stmt = stmt.where(Player.school == school)
    if search:
        stmt = stmt.where(Player.name.ilike(f"%{search}%"))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt)
    players = db.scalars(stmt.offset(offset).limit(limit)).all()
    return players, total or 0


def get_player(db: Session, player_id: int) -> Player | None:
    return db.get(Player, player_id)
