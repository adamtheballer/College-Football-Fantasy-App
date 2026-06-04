from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from api.app.api.deps import get_current_user
from api.app.db.session import get_db
from api.app.models.mock_draft_participant import MockDraftParticipant
from api.app.models.mock_draft_session import MockDraftSession
from api.app.models.user import User
from api.app.schemas.mock_draft import (
    MockDraftAutoPickRequest,
    MockDraftCreateRequest,
    MockDraftCreateResponse,
    MockDraftEmailHistoryRequest,
    MockDraftEmailHistoryResponse,
    MockDraftExitResponse,
    MockDraftHistoryRead,
    MockDraftJoinByCodeRequest,
    MockDraftJoinRequest,
    MockDraftLobbyRead,
    MockDraftLobbyReadyRequest,
    MockDraftPickCreate,
    MockDraftRecentList,
    MockDraftRoomRead,
    MockDraftSettingsUpdate,
)
from api.app.services import mock_draft_service


router = APIRouter()
MOCK_DRAFT_PUBLIC_INVITE_LENGTH = mock_draft_service.INVITE_CODE_LENGTH
MOCK_DRAFT_SEAT_FILL_SECONDS = 0
MOCK_DRAFT_ROOM_PREVIEW_SECONDS = mock_draft_service.INTERMISSION_SECONDS


def _mock_draft_session_or_404(db: Session, mock_draft_id: int) -> MockDraftSession:
    session_row = (
        db.query(MockDraftSession)
        .filter(MockDraftSession.id == mock_draft_id, MockDraftSession.deleted_at.is_(None))
        .first()
    )
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock draft not found.")
    return session_row


def _autopick_timed_out_current_seat(db: Session, *, session_row: MockDraftSession) -> bool:
    before_pick = int(session_row.current_overall_pick or 1)
    before_status = session_row.status
    try:
        mock_draft_service.make_auto_pick(db, mock_draft_id=session_row.id, current_user=None, force=False)
    except HTTPException:
        db.rollback()
        refreshed = db.get(MockDraftSession, session_row.id)
        if refreshed is None:
            return False
        mock_draft_service.advance_mock_draft_state(db, session_row=refreshed, now=datetime.now(timezone.utc))
        db.commit()
        return refreshed.status != before_status or int(refreshed.current_overall_pick or 1) != before_pick
    refreshed = db.get(MockDraftSession, session_row.id)
    return bool(refreshed and (refreshed.status != before_status or int(refreshed.current_overall_pick or 1) != before_pick))


@router.post("", response_model=MockDraftCreateResponse)
def create_mock_draft(
    payload: MockDraftCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftCreateResponse:
    return mock_draft_service.create_mock_draft(db, payload=payload, current_user=current_user)


@router.post("/join", response_model=MockDraftLobbyRead)
def join_mock_draft(
    payload: MockDraftJoinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftLobbyRead:
    return mock_draft_service.join_mock_draft_by_code(db, payload=payload, current_user=current_user)


@router.post("/join-with-code", response_model=MockDraftLobbyRead)
def join_mock_draft_legacy(
    payload: MockDraftJoinByCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftLobbyRead:
    return mock_draft_service.join_mock_draft_by_code(
        db,
        payload=MockDraftJoinRequest(invite_code=payload.invite_code),
        current_user=current_user,
    )


@router.post("/join-by-code", response_model=MockDraftLobbyRead)
def preview_or_join_mock_draft_legacy(
    payload: MockDraftJoinByCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftLobbyRead:
    return mock_draft_service.join_mock_draft_by_code(
        db,
        payload=MockDraftJoinRequest(invite_code=payload.invite_code),
        current_user=current_user,
    )


@router.get("/recent", response_model=MockDraftRecentList)
def recent_mock_drafts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRecentList:
    sessions = mock_draft_service.recent_mock_drafts(db, current_user=current_user)
    return MockDraftRecentList(
        data=[
            mock_draft_service.get_lobby_state(db, mock_draft_id=session_row.id, current_user=current_user)
            for session_row in sessions
        ]
    )


@router.get("/{mock_draft_id}/lobby", response_model=MockDraftLobbyRead)
def get_mock_draft_lobby(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftLobbyRead:
    return mock_draft_service.get_lobby_state(db, mock_draft_id=mock_draft_id, current_user=current_user)


@router.patch("/{mock_draft_id}/settings", response_model=MockDraftLobbyRead)
def update_mock_draft_settings(
    mock_draft_id: int,
    payload: MockDraftSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftLobbyRead:
    return mock_draft_service.update_settings_before_lock(
        db,
        mock_draft_id=mock_draft_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/{mock_draft_id}/ready", response_model=MockDraftLobbyRead)
def set_mock_draft_ready(
    mock_draft_id: int,
    payload: MockDraftLobbyReadyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftLobbyRead:
    session_row = _mock_draft_session_or_404(db, mock_draft_id)
    participant = (
        db.query(MockDraftParticipant)
        .filter(MockDraftParticipant.mock_draft_id == mock_draft_id, MockDraftParticipant.user_id == current_user.id)
        .first()
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Join this mock draft first.")
    if session_row.status not in {"scheduled", "lobby"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ready state is locked.")
    participant.is_ready = payload.ready
    participant.last_seen_at = datetime.now(timezone.utc)
    db.add(participant)
    mock_draft_service.log_mock_draft_event(
        db,
        mock_draft_id=mock_draft_id,
        event_type="participant_ready",
        payload={"participant_id": participant.id, "ready": payload.ready},
        created_by_user_id=current_user.id,
    )
    db.commit()
    return mock_draft_service.get_lobby_state(db, mock_draft_id=mock_draft_id, current_user=current_user)


@router.post("/{mock_draft_id}/start", response_model=MockDraftRoomRead)
def start_mock_draft_at_scheduled_time(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRoomRead:
    session_row = _mock_draft_session_or_404(db, mock_draft_id)
    if (session_row.host_user_id or session_row.commissioner_user_id) != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Host access required.")
    scheduled_start_at = mock_draft_service._as_utc(session_row.scheduled_start_at or session_row.draft_datetime_utc)
    now = datetime.now(timezone.utc)
    if scheduled_start_at and scheduled_start_at > now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Host cannot start early. The draft starts at the scheduled time.")
    mock_draft_service.advance_mock_draft_state(db, session_row=session_row, now=now)
    db.commit()
    return mock_draft_service.get_room_state(db, mock_draft_id=mock_draft_id, current_user=current_user)


@router.get("/{mock_draft_id}/room", response_model=MockDraftRoomRead)
def get_mock_draft_room(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRoomRead:
    return mock_draft_service.get_room_state(db, mock_draft_id=mock_draft_id, current_user=current_user)


@router.post("/{mock_draft_id}/picks", response_model=MockDraftRoomRead)
def make_mock_draft_pick(
    mock_draft_id: int,
    payload: MockDraftPickCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> MockDraftRoomRead:
    return mock_draft_service.make_human_pick(
        db,
        mock_draft_id=mock_draft_id,
        player_id=payload.player_id,
        current_user=current_user,
        idempotency_key=idempotency_key,
    )


@router.post("/{mock_draft_id}/pick", response_model=MockDraftRoomRead)
def make_mock_draft_pick_legacy(
    mock_draft_id: int,
    payload: MockDraftPickCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> MockDraftRoomRead:
    return make_mock_draft_pick(mock_draft_id, payload, db, current_user, idempotency_key)


@router.post("/{mock_draft_id}/auto-pick", response_model=MockDraftRoomRead)
def make_mock_draft_auto_pick(
    mock_draft_id: int,
    payload: MockDraftAutoPickRequest | None = None,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRoomRead:
    return mock_draft_service.make_auto_pick(
        db,
        mock_draft_id=mock_draft_id,
        current_user=current_user,
        force=bool(force or (payload.force if payload else False)),
    )


@router.get("/{mock_draft_id}/history", response_model=MockDraftHistoryRead)
def get_mock_draft_history(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftHistoryRead:
    return mock_draft_service.build_history(db, mock_draft_id=mock_draft_id, current_user=current_user)


@router.post("/{mock_draft_id}/history/email", response_model=MockDraftEmailHistoryResponse)
def email_mock_draft_history(
    mock_draft_id: int,
    _payload: MockDraftEmailHistoryRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftEmailHistoryResponse:
    return mock_draft_service.email_history(db, mock_draft_id=mock_draft_id, current_user=current_user)


@router.post("/{mock_draft_id}/email-summary", response_model=MockDraftEmailHistoryResponse)
def email_mock_draft_history_legacy(
    mock_draft_id: int,
    _payload: MockDraftEmailHistoryRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftEmailHistoryResponse:
    return mock_draft_service.email_history(db, mock_draft_id=mock_draft_id, current_user=current_user)


@router.post("/{mock_draft_id}/exit", response_model=MockDraftExitResponse)
def exit_mock_draft(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftExitResponse:
    return mock_draft_service.exit_mock_draft(db, mock_draft_id=mock_draft_id, current_user=current_user)


@router.delete("/{mock_draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mock_draft(
    mock_draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    session_row = _mock_draft_session_or_404(db, mock_draft_id)
    if (session_row.host_user_id or session_row.commissioner_user_id) != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Host access required.")
    session_row.deleted_at = datetime.now(timezone.utc)
    session_row.status = "cancelled"
    session_row.cancelled_at = datetime.now(timezone.utc)
    db.add(session_row)
    mock_draft_service.log_mock_draft_event(
        db,
        mock_draft_id=mock_draft_id,
        event_type="deleted",
        created_by_user_id=current_user.id,
    )
    db.commit()
