from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.schemas.player import PlayerCreate
from collegefootballfantasy_api.app.services.player_pool_filters import generated_test_player_filter


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
        requested_positions = [value.strip().upper() for value in position.split(",") if value.strip()]
        if len(requested_positions) == 1:
            stmt = stmt.where(Player.position == requested_positions[0])
        elif requested_positions:
            stmt = stmt.where(Player.position.in_(requested_positions))
    if school:
        stmt = stmt.where(Player.school == school)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Player.name.ilike(pattern) | Player.school.ilike(pattern) | Player.position.ilike(pattern))
    if league_id is not None and available_only:
        rostered_players = (
            select(RosterEntry.player_id)
            .join(Team, Team.id == RosterEntry.team_id)
            .where(Team.league_id == league_id)
        )
        draft_picked_players = (
            select(DraftPick.player_id)
            .join(Draft, Draft.id == DraftPick.draft_id)
            .where(Draft.league_id == league_id, Draft.status.in_(("scheduled", "live", "active")))
        )
        stmt = stmt.where(Player.id.not_in(rostered_players), Player.id.not_in(draft_picked_players))

    if sort in {"adp", "draft_rank", "rank"}:
        invalid_adp_sort_bucket = case(
            (Player.sheet_adp.is_(None), 1),
            (Player.sheet_adp <= 0, 1),
            else_=0,
        )
        stmt = stmt.order_by(
            invalid_adp_sort_bucket.asc(),
            Player.sheet_adp.asc(),
            func.lower(Player.name).asc(),
            Player.id.asc(),
        )
    elif sort == "school":
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
