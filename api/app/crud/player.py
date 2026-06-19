from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.schemas.player import PlayerCreate
from collegefootballfantasy_api.app.services.player_pool_filters import generated_test_player_filter


def _player_board_sort_tuple(player: Player) -> tuple:
    return (
        player.sheet_adp is None,
        float(player.sheet_adp) if player.sheet_adp is not None and player.sheet_adp > 0 else 9_999_999.0,
        player.name.lower(),
        player.id,
    )


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
    stmt: Select = select(Player).where(generated_test_player_filter())
    if position:
        stmt = stmt.where(Player.position == position)
    if school:
        stmt = stmt.where(Player.school == school)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Player.name.ilike(pattern) | Player.school.ilike(pattern) | Player.position.ilike(pattern))
    if league_id is not None and available_only:
        unavailable_players = (
            select(RosterEntry.player_id)
            .join(Team, Team.id == RosterEntry.team_id)
            .where(Team.league_id == league_id)
        )
        stmt = stmt.where(Player.id.not_in(unavailable_players))

    if sort in {"adp", "draft_rank", "rank"}:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt)
        players = db.scalars(stmt).all()
        players.sort(key=_player_board_sort_tuple)
        return players[offset : offset + limit], total or 0
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
