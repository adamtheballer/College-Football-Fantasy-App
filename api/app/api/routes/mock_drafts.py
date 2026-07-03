from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.mock_draft import (
    MockDraftCreate,
    MockDraftList,
    MockDraftPickCreate,
    MockDraftRead,
)
from collegefootballfantasy_api.app.services.mock_draft_service import (
    MockDraftError,
    auto_pick_mock_draft,
    create_mock_draft,
    get_mock_draft,
    list_mock_drafts,
    make_mock_pick,
    reset_mock_draft,
)

router = APIRouter()


def _mock_draft_http_error(error: MockDraftError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))


@router.get("", response_model=MockDraftList)
def list_my_mock_drafts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftList:
    data = list_mock_drafts(db, current_user.id)
    return MockDraftList(data=data, total=len(data))


@router.post("", response_model=MockDraftRead, status_code=status.HTTP_201_CREATED)
def create_my_mock_draft(
    payload: MockDraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRead:
    return create_mock_draft(db, current_user.id, payload)


@router.get("/{mock_draft_id}", response_model=MockDraftRead)
def get_my_mock_draft(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRead:
    try:
        return get_mock_draft(db, mock_draft_id, current_user.id)
    except MockDraftError as exc:
        raise _mock_draft_http_error(exc) from exc


@router.post("/{mock_draft_id}/picks", response_model=MockDraftRead)
def create_my_mock_pick(
    mock_draft_id: int,
    payload: MockDraftPickCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRead:
    try:
        return make_mock_pick(db, mock_draft_id, current_user.id, payload.player_id)
    except MockDraftError as exc:
        raise _mock_draft_http_error(exc) from exc


@router.post("/{mock_draft_id}/auto-pick", response_model=MockDraftRead)
def create_my_mock_auto_pick(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRead:
    try:
        return auto_pick_mock_draft(db, mock_draft_id, current_user.id)
    except MockDraftError as exc:
        raise _mock_draft_http_error(exc) from exc


@router.post("/{mock_draft_id}/reset", response_model=MockDraftRead)
def reset_my_mock_draft(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRead:
    try:
        return reset_mock_draft(db, mock_draft_id, current_user.id)
    except MockDraftError as exc:
        raise _mock_draft_http_error(exc) from exc
