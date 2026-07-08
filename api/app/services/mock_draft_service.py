from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from collegefootballfantasy_api.app.domain.draft_rules import snake_pick_for_number
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.mock_draft import MockDraft
from collegefootballfantasy_api.app.models.mock_draft_pick import MockDraftPick
from collegefootballfantasy_api.app.models.mock_draft_queue_entry import MockDraftQueueEntry
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.schemas.mock_draft import MockDraftCreate, MockDraftExport, MockDraftExportTeam


class MockDraftError(Exception):
    status_code = 400


class MockDraftNotFound(MockDraftError):
    status_code = 404


class MockDraftConflict(MockDraftError):
    status_code = 409


DEFAULT_MOCK_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "BENCH": 5,
}

POSITION_NEED_ORDER = ["QB", "RB", "WR", "TE", "K"]


def _team_name(team_index: int, user_team_index: int = 1) -> str:
    if team_index == user_team_index:
        return "Your Team"
    return f"Bot Team {team_index}"


def _total_picks(mock_draft: MockDraft) -> int:
    return int(mock_draft.league_size) * int(mock_draft.rounds)


def _roster_slots(mock_draft: MockDraft) -> dict[str, int]:
    settings = mock_draft.settings_json or {}
    raw_slots = settings.get("roster_slots_json") or settings.get("roster_slots") or DEFAULT_MOCK_ROSTER_SLOTS
    return {str(key).upper(): int(value or 0) for key, value in raw_slots.items()}


def _source_league_settings(db: Session, league_id: int, owner_user_id: int) -> dict | None:
    membership = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == owner_user_id)
        .first()
    )
    if not membership:
        raise MockDraftNotFound("source league not found")
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings_row:
        raise MockDraftNotFound("source league settings not found")
    return {
        "source_league_id": league_id,
        "scoring_json": settings_row.scoring_json,
        "roster_slots_json": settings_row.roster_slots_json,
        "superflex_enabled": settings_row.superflex_enabled,
        "kicker_enabled": settings_row.kicker_enabled,
    }


def _current_pick_context(mock_draft: MockDraft) -> tuple[int, int, int]:
    return snake_pick_for_number(mock_draft.current_pick, mock_draft.league_size)


def _picked_player_ids(db: Session, mock_draft_id: int) -> set[int]:
    rows = db.query(MockDraftPick.player_id).filter(MockDraftPick.mock_draft_id == mock_draft_id).all()
    return {int(row[0]) for row in rows}


def _team_position_counts(db: Session, mock_draft_id: int, team_index: int) -> dict[str, int]:
    rows = (
        db.query(MockDraftPick.player_position)
        .filter(MockDraftPick.mock_draft_id == mock_draft_id, MockDraftPick.team_index == team_index)
        .all()
    )
    counts: dict[str, int] = {}
    for row in rows:
        position = str(row[0]).upper()
        counts[position] = counts.get(position, 0) + 1
    return counts


def _target_position_for_team(db: Session, mock_draft: MockDraft, team_index: int) -> str | None:
    slot_limits = _roster_slots(mock_draft)
    counts = _team_position_counts(db, mock_draft.id, team_index)
    for position in POSITION_NEED_ORDER:
        if slot_limits.get(position, 0) > counts.get(position, 0):
            return position
    flex_total = int(slot_limits.get("FLEX", 0) or 0)
    if flex_total:
        flex_count = sum(counts.get(position, 0) for position in ("RB", "WR", "TE"))
        base_flex_capacity = sum(int(slot_limits.get(position, 0) or 0) for position in ("RB", "WR", "TE")) + flex_total
        if flex_count < base_flex_capacity:
            return "RB"
    return None


def _available_players_query(db: Session, mock_draft: MockDraft):
    picked_ids = _picked_player_ids(db, mock_draft.id)
    query = db.query(Player)
    if picked_ids:
        query = query.filter(~Player.id.in_(picked_ids))
    return query.order_by(
        Player.sheet_adp.is_(None),
        Player.sheet_adp.asc(),
        Player.sheet_projected_season_points.desc().nullslast(),
        Player.id.asc(),
    )


def _queued_candidate(db: Session, mock_draft: MockDraft) -> Player | None:
    picked_ids = _picked_player_ids(db, mock_draft.id)
    queue_rows = (
        db.query(MockDraftQueueEntry)
        .filter(MockDraftQueueEntry.mock_draft_id == mock_draft.id)
        .order_by(MockDraftQueueEntry.priority.asc(), MockDraftQueueEntry.id.asc())
        .all()
    )
    for queue_row in queue_rows:
        if queue_row.player_id in picked_ids:
            continue
        player = db.get(Player, queue_row.player_id)
        if player:
            return player
    return None


def _cpu_candidate(db: Session, mock_draft: MockDraft, team_index: int) -> Player | None:
    target_position = _target_position_for_team(db, mock_draft, team_index)
    players = _available_players_query(db, mock_draft).all()
    if target_position:
        for player in players:
            if player.position.upper() == target_position:
                return player
    return players[0] if players else None


def _create_pick(db: Session, mock_draft: MockDraft, player: Player, *, auto: bool) -> MockDraftPick:
    if mock_draft.status != "active":
        raise MockDraftConflict("mock draft is not active")
    total_picks = _total_picks(mock_draft)
    if mock_draft.current_pick > total_picks:
        mock_draft.status = "completed"
        mock_draft.completed_at = datetime.now(UTC)
        db.flush()
        raise MockDraftConflict("mock draft is already complete")
    already_picked = (
        db.query(MockDraftPick.id)
        .filter(MockDraftPick.mock_draft_id == mock_draft.id, MockDraftPick.player_id == player.id)
        .first()
    )
    if already_picked:
        raise MockDraftConflict("player already picked in this mock draft")

    round_number, round_pick, team_index = _current_pick_context(mock_draft)
    pick = MockDraftPick(
        mock_draft_id=mock_draft.id,
        player_id=player.id,
        pick_number=mock_draft.current_pick,
        round_number=round_number,
        round_pick=round_pick,
        team_index=team_index,
        team_name=_team_name(team_index, mock_draft.user_team_index),
        player_name=player.name,
        player_school=player.school,
        player_position=player.position,
    )
    db.add(pick)
    mock_draft.current_pick += 1
    if mock_draft.current_pick > total_picks:
        mock_draft.status = "completed"
        mock_draft.completed_at = datetime.now(UTC)
    db.flush()
    return pick


def _advance_cpu_until_user_turn_or_complete(db: Session, mock_draft: MockDraft) -> None:
    while mock_draft.status == "active" and mock_draft.current_pick <= _total_picks(mock_draft):
        _round_number, _round_pick, team_index = _current_pick_context(mock_draft)
        if team_index == mock_draft.user_team_index:
            break
        player = _cpu_candidate(db, mock_draft, team_index)
        if not player:
            raise MockDraftConflict("no available players remain")
        _create_pick(db, mock_draft, player, auto=True)


def get_mock_draft(db: Session, mock_draft_id: int, owner_user_id: int) -> MockDraft:
    mock_draft = (
        db.query(MockDraft)
        .options(selectinload(MockDraft.picks), selectinload(MockDraft.queue))
        .filter(MockDraft.id == mock_draft_id, MockDraft.owner_user_id == owner_user_id)
        .first()
    )
    if not mock_draft:
        raise MockDraftNotFound("mock draft not found")
    mock_draft.picks.sort(key=lambda pick: pick.pick_number)
    mock_draft.queue.sort(key=lambda row: row.priority)
    return mock_draft


def list_mock_drafts(db: Session, owner_user_id: int) -> list[MockDraft]:
    rows = (
        db.query(MockDraft)
        .options(selectinload(MockDraft.picks), selectinload(MockDraft.queue))
        .filter(MockDraft.owner_user_id == owner_user_id)
        .order_by(MockDraft.created_at.desc(), MockDraft.id.desc())
        .all()
    )
    for row in rows:
        row.picks.sort(key=lambda pick: pick.pick_number)
        row.queue.sort(key=lambda queue_row: queue_row.priority)
    return rows


def create_mock_draft(db: Session, owner_user_id: int, payload: MockDraftCreate) -> MockDraft:
    settings_json = dict(payload.settings_json or {})
    if payload.source_league_id is not None:
        settings_json.update(_source_league_settings(db, payload.source_league_id, owner_user_id) or {})
    mock_draft = MockDraft(
        owner_user_id=owner_user_id,
        title=payload.title,
        league_size=payload.league_size,
        rounds=payload.rounds,
        user_team_index=payload.user_team_index,
        cpu_strategy=payload.cpu_strategy,
        current_pick=1,
        status="active",
        settings_json=settings_json,
    )
    db.add(mock_draft)
    db.commit()
    db.refresh(mock_draft)
    return get_mock_draft(db, mock_draft.id, owner_user_id)


def reset_mock_draft(db: Session, mock_draft_id: int, owner_user_id: int) -> MockDraft:
    mock_draft = get_mock_draft(db, mock_draft_id, owner_user_id)
    db.query(MockDraftPick).filter(MockDraftPick.mock_draft_id == mock_draft.id).delete()
    mock_draft.status = "active"
    mock_draft.current_pick = 1
    mock_draft.completed_at = None
    db.commit()
    return get_mock_draft(db, mock_draft.id, owner_user_id)


def resume_mock_draft(db: Session, mock_draft_id: int, owner_user_id: int) -> MockDraft:
    mock_draft = get_mock_draft(db, mock_draft_id, owner_user_id)
    if mock_draft.status == "completed" or mock_draft.completed_at is not None or mock_draft.current_pick > _total_picks(mock_draft):
        raise MockDraftConflict("completed mock draft cannot be resumed")
    mock_draft.status = "active"
    db.commit()
    return get_mock_draft(db, mock_draft.id, owner_user_id)


def update_mock_draft_queue(db: Session, mock_draft_id: int, owner_user_id: int, player_ids: list[int]) -> MockDraft:
    mock_draft = get_mock_draft(db, mock_draft_id, owner_user_id)
    seen: set[int] = set()
    for player_id in player_ids:
        if player_id in seen:
            raise MockDraftConflict("duplicate player in mock draft queue")
        seen.add(player_id)
        if not db.get(Player, player_id):
            raise MockDraftNotFound("queued player not found")
    db.query(MockDraftQueueEntry).filter(MockDraftQueueEntry.mock_draft_id == mock_draft.id).delete()
    for index, player_id in enumerate(player_ids, start=1):
        db.add(MockDraftQueueEntry(mock_draft_id=mock_draft.id, player_id=player_id, priority=index))
    db.commit()
    return get_mock_draft(db, mock_draft.id, owner_user_id)


def make_mock_pick(db: Session, mock_draft_id: int, owner_user_id: int, player_id: int) -> MockDraft:
    mock_draft = get_mock_draft(db, mock_draft_id, owner_user_id)
    _round_number, _round_pick, team_index = _current_pick_context(mock_draft)
    if team_index != mock_draft.user_team_index:
        raise MockDraftConflict("CPU team is on the clock")
    player = db.get(Player, player_id)
    if not player:
        raise MockDraftNotFound("player not found")
    try:
        _create_pick(db, mock_draft, player, auto=False)
        _advance_cpu_until_user_turn_or_complete(db, mock_draft)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MockDraftConflict("mock draft pick conflict") from exc
    return get_mock_draft(db, mock_draft.id, owner_user_id)


def auto_pick_mock_draft(db: Session, mock_draft_id: int, owner_user_id: int) -> MockDraft:
    mock_draft = get_mock_draft(db, mock_draft_id, owner_user_id)
    _round_number, _round_pick, team_index = _current_pick_context(mock_draft)
    player = _queued_candidate(db, mock_draft) if team_index == mock_draft.user_team_index else None
    if not player:
        player = _cpu_candidate(db, mock_draft, team_index)
    if not player:
        raise MockDraftConflict("no available players remain")
    try:
        _create_pick(db, mock_draft, player, auto=True)
        _advance_cpu_until_user_turn_or_complete(db, mock_draft)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MockDraftConflict("mock draft pick conflict") from exc
    return get_mock_draft(db, mock_draft.id, owner_user_id)


def export_mock_draft_results(db: Session, mock_draft_id: int, owner_user_id: int) -> MockDraftExport:
    mock_draft = get_mock_draft(db, mock_draft_id, owner_user_id)
    teams: list[MockDraftExportTeam] = []
    for team_index in range(1, mock_draft.league_size + 1):
        picks = [pick for pick in mock_draft.picks if pick.team_index == team_index]
        teams.append(
            MockDraftExportTeam(
                team_index=team_index,
                team_name=_team_name(team_index, mock_draft.user_team_index),
                picks=picks,
            )
        )
    return MockDraftExport(
        mock_draft_id=mock_draft.id,
        title=mock_draft.title,
        status=mock_draft.status,
        league_size=mock_draft.league_size,
        rounds=mock_draft.rounds,
        settings_json=mock_draft.settings_json,
        teams=teams,
    )
