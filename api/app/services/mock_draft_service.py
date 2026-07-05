from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from collegefootballfantasy_api.app.models.mock_draft import MockDraft
from collegefootballfantasy_api.app.models.mock_draft_pick import MockDraftPick
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.schemas.mock_draft import MockDraftCreate


class MockDraftError(Exception):
    status_code = 400


class MockDraftNotFound(MockDraftError):
    status_code = 404


class MockDraftConflict(MockDraftError):
    status_code = 409


def _round_pick_for_pick(pick_number: int, league_size: int) -> tuple[int, int, int]:
    round_number = ((pick_number - 1) // league_size) + 1
    slot_index = (pick_number - 1) % league_size
    round_pick = slot_index + 1 if round_number % 2 == 1 else league_size - slot_index
    team_index = round_pick
    return round_number, round_pick, team_index


def _team_name(team_index: int, user_team_index: int = 1) -> str:
    if team_index == user_team_index:
        return "Your Team"
    return f"Bot Team {team_index}"


def get_mock_draft(db: Session, mock_draft_id: int, owner_user_id: int) -> MockDraft:
    mock_draft = (
        db.query(MockDraft)
        .options(selectinload(MockDraft.picks))
        .filter(MockDraft.id == mock_draft_id, MockDraft.owner_user_id == owner_user_id)
        .first()
    )
    if not mock_draft:
        raise MockDraftNotFound("mock draft not found")
    return mock_draft


def list_mock_drafts(db: Session, owner_user_id: int) -> list[MockDraft]:
    return (
        db.query(MockDraft)
        .options(selectinload(MockDraft.picks))
        .filter(MockDraft.owner_user_id == owner_user_id)
        .order_by(MockDraft.created_at.desc(), MockDraft.id.desc())
        .all()
    )


def create_mock_draft(db: Session, owner_user_id: int, payload: MockDraftCreate) -> MockDraft:
    mock_draft = MockDraft(
        owner_user_id=owner_user_id,
        title=payload.title,
        league_size=payload.league_size,
        rounds=payload.rounds,
        current_pick=1,
        status="active",
        settings_json=payload.settings_json,
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


def make_mock_pick(db: Session, mock_draft_id: int, owner_user_id: int, player_id: int) -> MockDraft:
    mock_draft = get_mock_draft(db, mock_draft_id, owner_user_id)
    if mock_draft.status != "active":
        raise MockDraftConflict("mock draft is not active")

    total_picks = mock_draft.league_size * mock_draft.rounds
    if mock_draft.current_pick > total_picks:
        mock_draft.status = "completed"
        mock_draft.completed_at = datetime.now(UTC)
        db.commit()
        raise MockDraftConflict("mock draft is already complete")

    player = db.get(Player, player_id)
    if not player:
        raise MockDraftNotFound("player not found")

    already_picked = (
        db.query(MockDraftPick.id)
        .filter(MockDraftPick.mock_draft_id == mock_draft.id, MockDraftPick.player_id == player_id)
        .first()
    )
    if already_picked:
        raise MockDraftConflict("player already picked in this mock draft")

    round_number, round_pick, team_index = _round_pick_for_pick(
        mock_draft.current_pick, mock_draft.league_size
    )
    pick = MockDraftPick(
        mock_draft_id=mock_draft.id,
        player_id=player.id,
        pick_number=mock_draft.current_pick,
        round_number=round_number,
        round_pick=round_pick,
        team_index=team_index,
        team_name=_team_name(team_index),
        player_name=player.name,
        player_school=player.school,
        player_position=player.position,
    )
    db.add(pick)
    mock_draft.current_pick += 1
    if mock_draft.current_pick > total_picks:
        mock_draft.status = "completed"
        mock_draft.completed_at = datetime.now(UTC)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MockDraftConflict("mock draft pick conflict") from exc

    return get_mock_draft(db, mock_draft.id, owner_user_id)


def auto_pick_mock_draft(db: Session, mock_draft_id: int, owner_user_id: int) -> MockDraft:
    mock_draft = get_mock_draft(db, mock_draft_id, owner_user_id)
    picked_player_ids = (
        db.query(MockDraftPick.player_id).filter(MockDraftPick.mock_draft_id == mock_draft.id).subquery()
    )
    player = (
        db.query(Player)
        .filter(~Player.id.in_(picked_player_ids))
        .order_by(
            Player.sheet_adp.is_(None),
            Player.sheet_adp.asc(),
            Player.sheet_projected_season_points.desc().nullslast(),
            Player.name.asc(),
        )
        .first()
    )
    if not player:
        raise MockDraftConflict("no available players remain")
    return make_mock_pick(db, mock_draft.id, owner_user_id, player.id)
