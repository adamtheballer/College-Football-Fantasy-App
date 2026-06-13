import re

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from api.app.models.draft import Draft
from api.app.models.draft_pick import DraftPick
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.schemas.player import PlayerCreate
from api.app.services.player_identity import player_board_sort_tuple, player_canonical_key, prefer_canonical_player
from api.app.services.player_pool_filters import generated_test_player_filter


def create_players(db: Session, players_in: list[PlayerCreate]) -> list[Player]:
    players = [Player(**player.model_dump()) for player in players_in]
    db.add_all(players)
    db.commit()
    for player in players:
        db.refresh(player)
    return players


def _player_sort_key(player: Player, sort: str | None) -> tuple:
    if sort in {"adp", "draft_rank", "rank"}:
        return player_board_sort_tuple(player)
    if sort in {"projection", "fantasy_points", "projected_fantasy_points"}:
        projection = -(float(player.sheet_projected_season_points) if player.sheet_projected_season_points is not None else 0.0)
        return (
            projection,
            player.sheet_adp is None,
            float(player.sheet_adp) if player.sheet_adp is not None and player.sheet_adp > 0 else 9_999_999.0,
            player.name.lower(),
            player.id,
        )
    if sort == "school":
        return (player.school.lower(), player.name.lower(), player.id)
    if sort == "position":
        return (player.position.upper(), player.name.lower(), player.id)
    if sort == "name":
        return (player.name.lower(), player.id)
    return player_board_sort_tuple(player)


def _canonical_unavailable_player_keys(db: Session, league_id: int) -> set[tuple[str, str, str]]:
    rostered_players = (
        db.query(Player)
        .join(RosterEntry, RosterEntry.player_id == Player.id)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league_id)
        .all()
    )
    drafted_players = (
        db.query(Player)
        .join(DraftPick, DraftPick.player_id == Player.id)
        .join(Draft, Draft.id == DraftPick.draft_id)
        .filter(Draft.league_id == league_id)
        .all()
    )
    return {player_canonical_key(player) for player in [*rostered_players, *drafted_players]}


def _canonicalize_players(
    players: list[Player],
    *,
    unavailable_keys: set[tuple[str, str, str]] | None = None,
) -> list[Player]:
    unavailable_keys = unavailable_keys or set()
    by_key: dict[tuple[str, str, str], Player] = {}
    for player in players:
        key = player_canonical_key(player)
        if key in unavailable_keys:
            continue
        current = by_key.get(key)
        by_key[key] = prefer_canonical_player(current, player) if current else player
    return list(by_key.values())


def list_players(
    db: Session,
    limit: int,
    offset: int,
    position: str | None,
    school: str | None,
    search: str | None,
    league_id: int | None = None,
    available_in_league_id: int | None = None,
    available_only: bool = False,
    sort: str | None = None,
) -> tuple[list[Player], int]:
    stmt: Select = select(Player).where(generated_test_player_filter())
    if position:
        stmt = stmt.where(func.upper(Player.position) == position.upper())
    if school:
        stmt = stmt.where(Player.school.ilike(school))
    if search:
        # Tokenized search supports names with middle names/hyphens
        # (e.g. "Ryan Williams" matches "Ryan Coleman-Williams").
        tokens = [token for token in re.split(r"[\s,./-]+", search.strip()) if token]
        if tokens:
            term_clauses = []
            for token in tokens:
                pattern = f"%{token}%"
                term_clauses.append(
                    or_(
                        Player.name.ilike(pattern),
                        Player.school.ilike(pattern),
                        Player.position.ilike(pattern),
                    )
                )
            stmt = stmt.where(and_(*term_clauses))
    effective_available_league_id = available_in_league_id if available_in_league_id is not None else league_id
    unavailable_keys = (
        _canonical_unavailable_player_keys(db, effective_available_league_id)
        if effective_available_league_id is not None and (available_only or available_in_league_id is not None)
        else set()
    )

    canonical_players = _canonicalize_players(db.scalars(stmt).all(), unavailable_keys=unavailable_keys)
    canonical_players.sort(key=lambda player: _player_sort_key(player, sort))
    total = len(canonical_players)
    return canonical_players[offset : offset + limit], total


def get_player(db: Session, player_id: int) -> Player | None:
    return db.get(Player, player_id)
