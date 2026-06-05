from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlparse

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.app.core.config import settings
from api.app.models.mock_draft_event import MockDraftEvent
from api.app.models.mock_draft_participant import MockDraftParticipant
from api.app.models.mock_draft_pick import MockDraftPick
from api.app.models.mock_draft_session import MockDraftSession
from api.app.models.player import Player
from api.app.models.user import User
from api.app.schemas.mock_draft import (
    MockDraftCreateRequest,
    MockDraftCreateResponse,
    MockDraftEmailHistoryResponse,
    MockDraftExitResponse,
    MockDraftHistoryRead,
    MockDraftJoinRequest,
    MockDraftLobbyRead,
    MockDraftParticipantRead,
    MockDraftPickRead,
    MockDraftRoomRead,
    MockDraftRosterRead,
    MockDraftSessionSummary,
    MockDraftSettingsUpdate,
)
from api.app.schemas.player import PlayerList
from api.app.services.draft_engine import (
    calculate_total_picks,
    get_participant_for_pick,
    get_round_number,
    get_round_pick,
    get_total_picks,
    is_final_pick,
)
from api.app.services.draft_timer import clear_timer_on_completion, is_timer_expired, reset_pick_timer_after_pick, seconds_remaining, start_pick_timer
from api.app.services.invite_links import build_mock_draft_invite_link, generate_invite_token
from api.app.services.league_flow import FIXED_ROSTER_SLOTS
from api.app.services.mock_draft_history import build_mock_draft_history


INVITE_CODE_LENGTH = 128
INTERMISSION_SECONDS = 30
SINGLE_PLAYER_PRE_DRAFT_SECONDS = 90
BOT_PICK_DELAY_SECONDS = 1
OFFENSE_POSITIONS = ("QB", "RB", "WR", "TE", "K")
JOINABLE_STATUSES = {"scheduled", "lobby"}
LOCKED_STATUSES = {"intermission", "live", "paused", "completed", "cancelled", "expired", "pending_deletion"}


def _fixed_mock_round_count() -> int:
    return max(1, get_total_picks(1, FIXED_ROSTER_SLOTS))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _display_name(user: User, fallback: str = "Manager") -> str:
    name = (user.first_name or "").strip()
    if name:
        return name
    email_prefix = (user.email or "").split("@", 1)[0].strip()
    return email_prefix or fallback


def _mock_draft_mode(session_row: MockDraftSession) -> str:
    return session_row.mode or "public_multiplayer"


def _is_public_multiplayer(session_row: MockDraftSession) -> bool:
    return _mock_draft_mode(session_row) == "public_multiplayer"


def _join_url(invite_code: str | None) -> str | None:
    if not invite_code:
        return None
    return build_mock_draft_invite_link(invite_code)


def normalize_invite_code(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        if parsed.path:
            path_parts = [unquote(part) for part in parsed.path.split("/") if part]
            if len(path_parts) >= 4 and path_parts[-4:-1] == ["draft", "mock", "invite"]:
                return path_parts[-1].strip()
        query = parse_qs(parsed.query)
        if query.get("code"):
            return query["code"][0].strip()
    return raw


def generate_unique_invite_code(db: Session) -> str:
    for _ in range(50):
        code = generate_invite_token()
        exists = db.query(MockDraftSession.id).filter(MockDraftSession.invite_code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to generate mock draft invite code.")


def log_mock_draft_event(
    db: Session,
    *,
    mock_draft_id: int,
    event_type: str,
    payload: dict | None = None,
    created_by_user_id: int | None = None,
) -> MockDraftEvent:
    event = MockDraftEvent(
        session_id=mock_draft_id,
        mock_draft_id=mock_draft_id,
        event_type=event_type,
        entity_type="mock_draft",
        entity_id=mock_draft_id,
        payload=payload or {},
        payload_json=payload or {},
        created_by_user_id=created_by_user_id,
    )
    db.add(event)
    db.flush()
    return event


def _get_session_or_404(db: Session, mock_draft_id: int, *, lock: bool = False) -> MockDraftSession:
    query = db.query(MockDraftSession).filter(MockDraftSession.id == mock_draft_id, MockDraftSession.deleted_at.is_(None))
    if lock:
        query = query.with_for_update()
    session_row = query.first()
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock draft not found.")
    return session_row


def _participants_query(db: Session, mock_draft_id: int):
    return db.query(MockDraftParticipant).filter(MockDraftParticipant.mock_draft_id == mock_draft_id)


def _ordered_participants(db: Session, mock_draft_id: int) -> list[MockDraftParticipant]:
    return (
        _participants_query(db, mock_draft_id)
        .order_by(
            case((MockDraftParticipant.draft_position.is_(None), 1), else_=0).asc(),
            MockDraftParticipant.draft_position.asc(),
            MockDraftParticipant.seat_number.asc(),
            MockDraftParticipant.id.asc(),
        )
        .all()
    )


def _participant_for_user(db: Session, mock_draft_id: int, user_id: int, *, lock: bool = False) -> MockDraftParticipant | None:
    query = _participants_query(db, mock_draft_id).filter(MockDraftParticipant.user_id == user_id)
    if lock:
        query = query.with_for_update()
    return query.first()


def _require_participant(db: Session, session_row: MockDraftSession, current_user: User) -> MockDraftParticipant:
    participant = _participant_for_user(db, session_row.id, current_user.id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Join this mock draft before entering.")
    return participant


def _participant_read(row: MockDraftParticipant) -> MockDraftParticipantRead:
    return MockDraftParticipantRead(
        id=row.id,
        mock_draft_id=row.mock_draft_id,
        user_id=row.user_id,
        display_name=row.display_name,
        team_name=row.team_name,
        participant_type=row.participant_type,  # type: ignore[arg-type]
        seat_number=row.seat_number,
        draft_position=row.draft_position,
        is_host=bool(row.is_host),
        is_ready=bool(row.is_ready),
        joined_at=row.joined_at,
        left_at=row.left_at,
        last_seen_at=row.last_seen_at,
        connection_status=row.connection_status,
        auto_pick_count=int(row.auto_pick_count or 0),
    )


def _session_summary(session_row: MockDraftSession) -> MockDraftSessionSummary:
    scheduled_start_at = _as_utc(session_row.scheduled_start_at or session_row.draft_datetime_utc) or _now()
    return MockDraftSessionSummary(
        id=session_row.id,
        name=session_row.name,
        mode=_mock_draft_mode(session_row),  # type: ignore[arg-type]
        invite_code=session_row.invite_code,
        status=session_row.status,  # type: ignore[arg-type]
        team_count=int(session_row.team_count or session_row.manager_count or 12),
        round_count=int(session_row.round_count or 13),
        draft_type=session_row.draft_type,
        pick_timer_seconds=int(session_row.pick_timer_seconds),
        scheduled_start_at=scheduled_start_at,
        intermission_started_at=session_row.intermission_started_at,
        intermission_ends_at=session_row.intermission_ends_at,
        started_at=session_row.started_at,
        completed_at=session_row.completed_at,
        expires_at=session_row.expires_at,
        player_pool=session_row.player_pool,
        scoring_type=session_row.scoring_type,
        bot_difficulty=session_row.bot_difficulty,
        draft_order_locked=bool(session_row.draft_order_locked),
        should_preserve_history=bool(session_row.should_preserve_history),
    )


def create_mock_draft(db: Session, *, payload: MockDraftCreateRequest, current_user: User) -> MockDraftCreateResponse:
    now = _now()
    mode = payload.mode
    round_count = _fixed_mock_round_count()
    invite_code = generate_unique_invite_code(db) if mode == "public_multiplayer" else None
    scheduled_start_at = (_as_utc(payload.scheduled_start_at) or payload.scheduled_start_at).astimezone(timezone.utc)
    effective_start_at = now if mode == "single_player" else scheduled_start_at
    session_row = MockDraftSession(
        commissioner_user_id=current_user.id,
        host_user_id=current_user.id,
        invite_code=invite_code,
        name=payload.name.strip(),
        mode=mode,
        status="lobby",
        manager_count=payload.team_count,
        team_count=payload.team_count,
        round_count=round_count,
        draft_type="snake",
        pick_timer_seconds=payload.pick_timer_seconds,
        roster_slots_json=FIXED_ROSTER_SLOTS.copy(),
        scoring_json={"mock": True, "scoring_type": payload.scoring_type},
        is_locked=False,
        draft_datetime_utc=effective_start_at,
        scheduled_start_at=effective_start_at,
        current_overall_pick=1,
        player_pool=payload.player_pool,
        scoring_type=payload.scoring_type,
        bot_difficulty=payload.bot_difficulty,
    )
    db.add(session_row)
    db.flush()
    host_name = _display_name(current_user)
    host = MockDraftParticipant(
        mock_draft_id=session_row.id,
        user_id=current_user.id,
        display_name=host_name,
        team_name=f"{host_name}'s Team",
        participant_type="human",
        seat_number=1,
        is_host=True,
        is_ready=True,
        joined_at=now,
        last_seen_at=now,
        connection_status="connected",
    )
    db.add(host)
    db.flush()
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="created", created_by_user_id=current_user.id)
    log_mock_draft_event(
        db,
        mock_draft_id=session_row.id,
        event_type="participant_joined",
        payload={"participant_id": host.id, "user_id": current_user.id},
        created_by_user_id=current_user.id,
    )
    if mode == "single_player":
        fill_empty_seats_with_bots(db, session_row=session_row, now=now)
        randomize_draft_order_once(db, session_row=session_row)
        session_row.status = "intermission"
        session_row.current_overall_pick = 1
        session_row.intermission_started_at = now
        session_row.intermission_ends_at = now + timedelta(seconds=SINGLE_PLAYER_PRE_DRAFT_SECONDS)
        session_row.current_pick_started_at = None
        session_row.current_pick_expires_at = None
        db.add(session_row)
        log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="order_randomized", created_by_user_id=current_user.id)
        log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="intermission_started", created_by_user_id=current_user.id)
    db.commit()
    db.refresh(session_row)
    invite_link = _join_url(invite_code) if mode == "public_multiplayer" else None
    return MockDraftCreateResponse(
        mock_draft_id=session_row.id,
        id=session_row.id,
        mode=mode,
        invite_code=invite_code,
        invite_link=invite_link,
        join_url=invite_link,
        lobby_url=f"/draft/mock/{session_row.id}/lobby",
        status=session_row.status,  # type: ignore[arg-type]
        scheduled_start_at=effective_start_at,
    )


def _next_open_seat(db: Session, session_row: MockDraftSession) -> int:
    taken = {
        seat
        for (seat,) in _participants_query(db, session_row.id)
        .with_for_update()
        .with_entities(MockDraftParticipant.seat_number)
        .all()
    }
    for seat_number in range(1, int(session_row.team_count or session_row.manager_count) + 1):
        if seat_number not in taken:
            return seat_number
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mock draft is full.")


def join_mock_draft_by_code(db: Session, *, payload: MockDraftJoinRequest, current_user: User) -> MockDraftLobbyRead:
    code = normalize_invite_code(payload.invite_code)
    if len(code) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid mock draft invite code.")
    session_row = (
        db.query(MockDraftSession)
        .filter(
            MockDraftSession.invite_code == code,
            MockDraftSession.mode == "public_multiplayer",
            MockDraftSession.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if session_row is None and code.isalnum():
        session_row = (
            db.query(MockDraftSession)
            .filter(
                func.upper(MockDraftSession.invite_code) == code.upper(),
                MockDraftSession.mode == "public_multiplayer",
                MockDraftSession.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock draft invite code not found.")
    advance_mock_draft_state(db, session_row=session_row, now=_now())
    if session_row.status not in JOINABLE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mock draft is already locked.")
    if _participant_for_user(db, session_row.id, current_user.id, lock=True) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already joined this mock draft.")
    seat_number = _next_open_seat(db, session_row)
    display_name = (payload.display_name or "").strip() or _display_name(current_user)
    team_name = (payload.team_name or "").strip() or f"{display_name}'s Team"
    now = _now()
    participant = MockDraftParticipant(
        mock_draft_id=session_row.id,
        user_id=current_user.id,
        display_name=display_name,
        team_name=team_name,
        participant_type="human",
        seat_number=seat_number,
        is_host=False,
        is_ready=False,
        joined_at=now,
        last_seen_at=now,
        connection_status="connected",
    )
    db.add(participant)
    db.flush()
    log_mock_draft_event(
        db,
        mock_draft_id=session_row.id,
        event_type="participant_joined",
        payload={"participant_id": participant.id, "user_id": current_user.id},
        created_by_user_id=current_user.id,
    )
    db.commit()
    return get_lobby_state(db, mock_draft_id=session_row.id, current_user=current_user)


def update_settings_before_lock(
    db: Session,
    *,
    mock_draft_id: int,
    payload: MockDraftSettingsUpdate,
    current_user: User,
) -> MockDraftLobbyRead:
    session_row = _get_session_or_404(db, mock_draft_id, lock=True)
    if (session_row.host_user_id or session_row.commissioner_user_id) != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Host access required.")
    advance_mock_draft_state(db, session_row=session_row, now=_now())
    if session_row.status not in JOINABLE_STATUSES or session_row.draft_order_locked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mock draft settings are locked.")
    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        if value is None:
            continue
        if field_name == "round_count":
            session_row.round_count = _fixed_mock_round_count()
            continue
        if field_name == "team_count":
            joined_count = _participants_query(db, session_row.id).count()
            if int(value) < joined_count:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_count cannot be less than joined users")
            session_row.manager_count = int(value)
        if field_name == "scheduled_start_at":
            value = _as_utc(value)
            if value is None or value <= _now():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scheduled_start_at must be in the future")
            session_row.draft_datetime_utc = value
        setattr(session_row, field_name, value)
    session_row.round_count = _fixed_mock_round_count()
    session_row.roster_slots_json = FIXED_ROSTER_SLOTS.copy()
    db.add(session_row)
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="settings_updated", created_by_user_id=current_user.id)
    db.commit()
    return get_lobby_state(db, mock_draft_id=session_row.id, current_user=current_user)


def fill_empty_seats_with_bots(db: Session, *, session_row: MockDraftSession, now: datetime) -> None:
    existing_seats = {
        seat
        for (seat,) in _participants_query(db, session_row.id)
        .with_for_update()
        .with_entities(MockDraftParticipant.seat_number)
        .all()
    }
    for seat_number in range(1, int(session_row.team_count or session_row.manager_count) + 1):
        if seat_number in existing_seats:
            continue
        bot = MockDraftParticipant(
            mock_draft_id=session_row.id,
            user_id=None,
            display_name=f"Bot {seat_number}",
            team_name=f"Bot Team {seat_number}",
            participant_type="bot",
            seat_number=seat_number,
            is_host=False,
            is_ready=True,
            joined_at=now,
            last_seen_at=now,
            connection_status="connected",
        )
        db.add(bot)
    db.flush()


def randomize_draft_order_once(db: Session, *, session_row: MockDraftSession) -> None:
    if session_row.draft_order_locked:
        return
    participants = _participants_query(db, session_row.id).with_for_update().all()
    secure_random = secrets.SystemRandom()
    secure_random.shuffle(participants)
    for index, participant in enumerate(participants, start=1):
        participant.draft_position = index
        db.add(participant)
    session_row.draft_order_locked = True
    session_row.is_locked = True
    db.add(session_row)
    db.flush()


def start_intermission_at_scheduled_time(db: Session, *, session_row: MockDraftSession, now: datetime) -> bool:
    if session_row.status not in JOINABLE_STATUSES:
        return False
    scheduled_start_at = _as_utc(session_row.scheduled_start_at or session_row.draft_datetime_utc)
    if scheduled_start_at is None or scheduled_start_at > now:
        return False
    fill_empty_seats_with_bots(db, session_row=session_row, now=now)
    randomize_draft_order_once(db, session_row=session_row)
    session_row.status = "intermission"
    session_row.intermission_started_at = now
    session_row.intermission_ends_at = now + timedelta(seconds=INTERMISSION_SECONDS)
    session_row.current_pick_started_at = None
    session_row.current_pick_expires_at = None
    session_row.current_overall_pick = 1
    db.add(session_row)
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="order_randomized")
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="intermission_started")
    return True


def transition_intermission_to_live(db: Session, *, session_row: MockDraftSession, now: datetime) -> bool:
    if session_row.status != "intermission":
        return False
    intermission_ends_at = _as_utc(session_row.intermission_ends_at)
    if intermission_ends_at is None or intermission_ends_at > now:
        return False
    session_row.status = "live"
    session_row.started_at = now
    session_row.current_overall_pick = max(1, int(session_row.current_overall_pick or 1))
    start_pick_timer(session_row, now)
    db.add(session_row)
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="draft_started")
    return True


def complete_mock_draft(db: Session, *, session_row: MockDraftSession, now: datetime) -> None:
    if session_row.status == "completed":
        return
    session_row.status = "completed"
    session_row.completed_at = now
    session_row.expires_at = now + timedelta(hours=settings.mock_draft_unsent_retention_hours)
    session_row.should_preserve_history = False
    clear_timer_on_completion(session_row)
    db.add(session_row)
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="draft_completed")


def advance_mock_draft_state(db: Session, *, session_row: MockDraftSession, now: datetime | None = None) -> bool:
    now = now or _now()
    changed = start_intermission_at_scheduled_time(db, session_row=session_row, now=now)
    if transition_intermission_to_live(db, session_row=session_row, now=now):
        changed = True
    total_picks = calculate_total_picks(int(session_row.team_count or session_row.manager_count), int(session_row.round_count or 13))
    if session_row.status == "live" and int(session_row.current_overall_pick or 1) > total_picks:
        complete_mock_draft(db, session_row=session_row, now=now)
        changed = True
    if changed:
        db.flush()
    return changed


def _current_participant(db: Session, session_row: MockDraftSession) -> MockDraftParticipant | None:
    participants = (
        _participants_query(db, session_row.id)
        .filter(MockDraftParticipant.draft_position.is_not(None))
        .order_by(MockDraftParticipant.draft_position.asc())
        .all()
    )
    return get_participant_for_pick(participants, int(session_row.current_overall_pick or 1))


def _available_players_query(db: Session, mock_draft_id: int):
    adp_missing = case((Player.sheet_adp.is_(None), 1), else_=0)
    adp_non_positive = case((Player.sheet_adp <= 0, 1), else_=0)
    projection_points = func.coalesce(Player.sheet_projected_season_points, -1.0)
    player_name_key = func.lower(Player.name)
    player_school_key = func.lower(Player.school)
    player_position_key = func.upper(Player.position)
    ranked_players = (
        db.query(
            Player.id.label("player_id"),
            func.row_number()
            .over(
                partition_by=(player_name_key, player_school_key, player_position_key),
                order_by=(
                    adp_missing.asc(),
                    adp_non_positive.asc(),
                    projection_points.desc(),
                    Player.sheet_adp.asc(),
                    Player.name.asc(),
                    Player.id.asc(),
                ),
            )
            .label("dedupe_rank"),
        )
        .filter(player_position_key.in_(OFFENSE_POSITIONS))
        .subquery()
    )
    picked_player_keys = (
        db.query(
            func.lower(Player.name).label("picked_name_key"),
            func.lower(Player.school).label("picked_school_key"),
            func.upper(Player.position).label("picked_position_key"),
        )
        .join(MockDraftPick, MockDraftPick.player_id == Player.id)
        .filter((MockDraftPick.mock_draft_id == mock_draft_id) | (MockDraftPick.session_id == mock_draft_id))
        .subquery()
    )
    return (
        db.query(Player)
        .join(ranked_players, ranked_players.c.player_id == Player.id)
        .outerjoin(
            picked_player_keys,
            and_(
                func.lower(Player.name) == picked_player_keys.c.picked_name_key,
                func.lower(Player.school) == picked_player_keys.c.picked_school_key,
                func.upper(Player.position) == picked_player_keys.c.picked_position_key,
            ),
        )
        .filter(ranked_players.c.dedupe_rank == 1)
        .filter(picked_player_keys.c.picked_name_key.is_(None))
        .order_by(
            adp_missing.asc(),
            adp_non_positive.asc(),
            Player.sheet_adp.asc(),
            projection_points.desc(),
            Player.name.asc(),
            Player.id.asc(),
        )
    )


def get_available_mock_players(
    db: Session,
    *,
    mock_draft_id: int,
    current_user: User,
    search: str | None = None,
    position: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PlayerList:
    session_row = _get_session_or_404(db, mock_draft_id)
    _require_participant(db, session_row, current_user)
    query = _available_players_query(db, session_row.id)
    board_rank_by_player_id = {
        player_id: index + 1
        for index, (player_id,) in enumerate(query.with_entities(Player.id).all())
    }
    if position:
        query = query.filter(func.upper(Player.position) == position.upper())
    if search:
        search_value = search.strip()
        if search_value:
            pattern = f"%{search_value}%"
            query = query.filter(
                or_(
                    Player.name.ilike(pattern),
                    Player.school.ilike(pattern),
                    Player.position.ilike(pattern),
                )
            )
    total = query.count()
    players = query.offset(offset).limit(limit).all()
    for player in players:
        setattr(player, "board_rank", board_rank_by_player_id.get(player.id))
    return PlayerList(data=players, total=total, limit=limit, offset=offset)


def _select_best_available_player(db: Session, mock_draft_id: int) -> Player:
    player = _available_players_query(db, mock_draft_id).with_for_update().first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No available players remain for auto-pick.")
    return player


def _pick_rows(db: Session, mock_draft_id: int) -> list[tuple[MockDraftPick, MockDraftParticipant, Player]]:
    return (
        db.query(MockDraftPick, MockDraftParticipant, Player)
        .join(MockDraftParticipant, MockDraftParticipant.id == MockDraftPick.participant_id)
        .join(Player, Player.id == MockDraftPick.player_id)
        .filter((MockDraftPick.mock_draft_id == mock_draft_id) | (MockDraftPick.session_id == mock_draft_id))
        .order_by(MockDraftPick.overall_pick.asc())
        .all()
    )


def _pick_read(pick: MockDraftPick, participant: MockDraftParticipant, player: Player) -> MockDraftPickRead:
    return MockDraftPickRead(
        id=pick.id,
        mock_draft_id=pick.mock_draft_id or pick.session_id,
        participant_id=participant.id,
        participant_name=participant.display_name,
        team_name=participant.team_name,
        player_id=player.id,
        player_name=player.name,
        player_position=player.position,
        player_school=player.school,
        overall_pick=pick.overall_pick,
        round_number=pick.round_number,
        round_pick=pick.round_pick,
        pick_source=pick.pick_source,  # type: ignore[arg-type]
        auto_pick_reason=pick.auto_pick_reason,
        made_by_user_id=pick.made_by_user_id,
        created_at=pick.created_at,
    )


def _room_pick_reads(db: Session, mock_draft_id: int) -> list[MockDraftPickRead]:
    return [_pick_read(pick, participant, player) for pick, participant, player in _pick_rows(db, mock_draft_id)]


def _rosters_from_picks(participants: list[MockDraftParticipantRead], picks: list[MockDraftPickRead]) -> list[MockDraftRosterRead]:
    picks_by_participant: dict[int, list[MockDraftPickRead]] = {}
    for pick in picks:
        picks_by_participant.setdefault(pick.participant_id, []).append(pick)
    return [
        MockDraftRosterRead(
            participant_id=participant.id,
            participant_name=participant.display_name,
            team_name=participant.team_name,
            picks=picks_by_participant.get(participant.id, []),
        )
        for participant in participants
    ]


def get_lobby_state(db: Session, *, mock_draft_id: int, current_user: User) -> MockDraftLobbyRead:
    session_row = _get_session_or_404(db, mock_draft_id, lock=True)
    advance_mock_draft_state(db, session_row=session_row, now=_now())
    participant = _participant_for_user(db, session_row.id, current_user.id)
    if participant:
        participant.last_seen_at = _now()
        participant.connection_status = "connected"
        db.add(participant)
    db.commit()
    db.refresh(session_row)
    participants = [_participant_read(row) for row in _ordered_participants(db, session_row.id)]
    now = _now()
    scheduled_start_at = _as_utc(session_row.scheduled_start_at or session_row.draft_datetime_utc) or now
    seconds_until_start = max(0, int((scheduled_start_at - now).total_seconds() + 0.999))
    is_host = bool((session_row.host_user_id or session_row.commissioner_user_id) == current_user.id)
    settings_locked = bool(session_row.draft_order_locked or session_row.status in LOCKED_STATUSES)
    can_join = bool(session_row.status in JOINABLE_STATUSES and len(participants) < int(session_row.team_count or session_row.manager_count))
    invite_link = _join_url(session_row.invite_code) if _is_public_multiplayer(session_row) else None
    return MockDraftLobbyRead(
        session=_session_summary(session_row),
        participants=participants,
        invite_code=session_row.invite_code if _is_public_multiplayer(session_row) else None,
        invite_link=invite_link,
        join_url=invite_link,
        server_time=now,
        seconds_until_start=seconds_until_start,
        is_current_user_host=is_host,
        settings_locked=settings_locked,
        can_join=can_join,
        can_leave=participant is not None and not bool(participant.is_host),
        can_edit_settings=is_host and not settings_locked,
        can_start_now=False,
        message="Host cannot start early. The draft starts at the scheduled time.",
        id=session_row.id,
        name=session_row.name,
        status=session_row.status,  # type: ignore[arg-type]
        team_count=int(session_row.team_count or session_row.manager_count),
        manager_count=int(session_row.team_count or session_row.manager_count),
        joined_count=len(participants),
        can_enter_room=bool(participant and session_row.status in {"intermission", "live", "paused", "completed"}),
        scheduled_start_at=scheduled_start_at,
    )


def get_room_state(db: Session, *, mock_draft_id: int, current_user: User) -> MockDraftRoomRead:
    session_row = _get_session_or_404(db, mock_draft_id, lock=True)
    participant = _require_participant(db, session_row, current_user)
    participant.last_seen_at = _now()
    participant.connection_status = "connected"
    db.add(participant)
    advance_mock_draft_state(db, session_row=session_row, now=_now())
    db.commit()
    db.refresh(session_row)
    participant_rows = _ordered_participants(db, session_row.id)
    participants = [_participant_read(row) for row in participant_rows]
    picks = _room_pick_reads(db, session_row.id)
    current = _current_participant(db, session_row)
    now = _now()
    total_picks = calculate_total_picks(int(session_row.team_count or session_row.manager_count), int(session_row.round_count or 13))
    current_overall_pick = min(max(1, int(session_row.current_overall_pick or 1)), total_picks)
    remaining = seconds_remaining(session_row, now) if session_row.status == "live" else None
    phase_type: str | None = None
    if session_row.status == "lobby":
        phase_type = "lobby_countdown"
    elif session_row.status == "intermission":
        phase_type = "prestart_countdown"
        intermission_ends_at = _as_utc(session_row.intermission_ends_at)
        remaining = max(0, int(((intermission_ends_at or now) - now).total_seconds() + 0.999))
    elif session_row.status == "live":
        phase_type = "pick_clock"
    elif session_row.status == "completed":
        phase_type = "complete"
    user_participant = _participant_for_user(db, session_row.id, current_user.id)
    available_count = _available_players_query(db, session_row.id).count()
    is_complete = session_row.status == "completed"
    return MockDraftRoomRead(
        session=_session_summary(session_row),
        server_time=now,
        participants=participants,
        picks=picks,
        rosters=_rosters_from_picks(participants, picks),
        draft_order=[participant.id for participant in participant_rows if participant.draft_position is not None],
        current_overall_pick=current_overall_pick,
        current_round=get_round_number(current_overall_pick, int(session_row.team_count or session_row.manager_count)),
        current_round_pick=get_round_pick(current_overall_pick, int(session_row.team_count or session_row.manager_count)),
        current_participant_id=current.id if current and not is_complete else None,
        current_participant_name=current.display_name if current and not is_complete else None,
        current_participant_type=current.participant_type if current and not is_complete else None,
        current_team_name=current.team_name if current and not is_complete else None,
        current_pick_started_at=session_row.current_pick_started_at,
        current_pick_expires_at=session_row.current_pick_expires_at,
        seconds_remaining=remaining,
        total_picks=total_picks,
        is_user_on_clock=bool(current and current.user_id == current_user.id and session_row.status == "live"),
        is_complete=is_complete,
        can_exit=bool(session_row.status in {"live", "paused", "completed"}),
        email_history_available=is_complete,
        should_show_email_prompt=bool(is_complete and not session_row.history_email_sent_at),
        available_player_count=int(available_count),
        mock_draft_id=session_row.id,
        status=session_row.status,  # type: ignore[arg-type]
        pick_timer_seconds=int(session_row.pick_timer_seconds),
        total_rounds=int(session_row.round_count or 13),
        current_pick=current_overall_pick,
        current_team_id=current.id if current and not is_complete else None,
        user_team_id=user_participant.id if user_participant else None,
        can_make_pick=bool(current and current.user_id == current_user.id and session_row.status == "live" and not is_timer_expired(session_row, now)),
        phase_type=phase_type,
    )


def _create_pick(
    db: Session,
    *,
    session_row: MockDraftSession,
    participant: MockDraftParticipant,
    player: Player,
    pick_source: str,
    auto_pick_reason: str | None,
    made_by_user_id: int | None,
    idempotency_key: str | None,
    now: datetime,
) -> MockDraftPick:
    overall_pick = int(session_row.current_overall_pick or 1)
    team_count = int(session_row.team_count or session_row.manager_count)
    existing_for_pick = (
        db.query(MockDraftPick)
        .filter(
            ((MockDraftPick.mock_draft_id == session_row.id) | (MockDraftPick.session_id == session_row.id)),
            MockDraftPick.overall_pick == overall_pick,
        )
        .first()
    )
    if existing_for_pick:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This pick has already been made.")
    existing_player = (
        db.query(MockDraftPick)
        .join(Player, Player.id == MockDraftPick.player_id)
        .filter(
            ((MockDraftPick.mock_draft_id == session_row.id) | (MockDraftPick.session_id == session_row.id)),
            func.lower(Player.name) == player.name.lower(),
            func.lower(Player.school) == player.school.lower(),
            func.upper(Player.position) == player.position.upper(),
        )
        .first()
    )
    if existing_player:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Player already drafted.")
    pick = MockDraftPick(
        session_id=session_row.id,
        mock_draft_id=session_row.id,
        participant_id=participant.id,
        seat_id=None,
        player_id=player.id,
        made_by_user_id=made_by_user_id,
        round_number=get_round_number(overall_pick, team_count),
        round_pick=get_round_pick(overall_pick, team_count),
        overall_pick=overall_pick,
        pick_source=pick_source,
        auto_pick_reason=auto_pick_reason,
        idempotency_key=idempotency_key,
    )
    db.add(pick)
    db.flush()
    total_picks = calculate_total_picks(team_count, int(session_row.round_count or 13))
    session_row.current_overall_pick = overall_pick + 1
    if is_final_pick(overall_pick, total_picks):
        complete_mock_draft(db, session_row=session_row, now=now)
    else:
        reset_pick_timer_after_pick(session_row, now)
    db.add(session_row)
    log_mock_draft_event(
        db,
        mock_draft_id=session_row.id,
        event_type="auto_pick_made" if pick_source in {"bot", "auto_timer"} else "pick_made",
        payload={"overall_pick": overall_pick, "player_id": player.id, "participant_id": participant.id, "source": pick_source},
        created_by_user_id=made_by_user_id,
    )
    return pick


def make_human_pick(
    db: Session,
    *,
    mock_draft_id: int,
    player_id: int,
    current_user: User,
    idempotency_key: str | None = None,
) -> MockDraftRoomRead:
    try:
        with db.begin_nested():
            session_row = _get_session_or_404(db, mock_draft_id, lock=True)
            advance_mock_draft_state(db, session_row=session_row, now=_now())
            if session_row.status != "live":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mock draft is not live.")
            now = _now()
            if is_timer_expired(session_row, now):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pick clock expired. Auto-pick will submit this turn.")
            current = _current_participant(db, session_row)
            if current is None or current.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not on the clock.")
            if idempotency_key:
                existing_for_key = (
                    db.query(MockDraftPick)
                    .filter(MockDraftPick.mock_draft_id == session_row.id, MockDraftPick.idempotency_key == idempotency_key)
                    .first()
                )
                if existing_for_key:
                    return get_room_state(db, mock_draft_id=session_row.id, current_user=current_user)
            player = db.query(Player).filter(Player.id == player_id).with_for_update().first()
            if player is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
            _create_pick(
                db,
                session_row=session_row,
                participant=current,
                player=player,
                pick_source="human",
                auto_pick_reason=None,
                made_by_user_id=current_user.id,
                idempotency_key=idempotency_key,
                now=now,
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate mock draft pick.") from exc
    return get_room_state(db, mock_draft_id=mock_draft_id, current_user=current_user)


def make_auto_pick(
    db: Session,
    *,
    mock_draft_id: int,
    current_user: User | None = None,
    force: bool = False,
    expected_overall_pick: int | None = None,
) -> MockDraftRoomRead:
    user_for_response = current_user
    try:
        with db.begin_nested():
            session_row = _get_session_or_404(db, mock_draft_id, lock=True)
            advance_mock_draft_state(db, session_row=session_row, now=_now())
            if session_row.status != "live":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mock draft is not live.")
            now = _now()
            if expected_overall_pick is not None and int(session_row.current_overall_pick or 1) != expected_overall_pick:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mock draft pick changed; refresh and retry.")
            current = _current_participant(db, session_row)
            if current is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No participant is on the clock.")
            if current.participant_type == "human" and not force and not is_timer_expired(session_row, now):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Human pick timer has not expired.")
            if current.participant_type == "bot" and not force:
                started_at = _as_utc(session_row.current_pick_started_at) or now
                if (now - started_at).total_seconds() < BOT_PICK_DELAY_SECONDS:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bot pick delay has not elapsed.")
            player = _select_best_available_player(db, session_row.id)
            current.auto_pick_count = int(current.auto_pick_count or 0) + 1
            db.add(current)
            source = "bot" if current.participant_type == "bot" else "auto_timer"
            reason = "bot_turn" if current.participant_type == "bot" else "timer_expired"
            _create_pick(
                db,
                session_row=session_row,
                participant=current,
                player=player,
                pick_source=source,
                auto_pick_reason=reason,
                made_by_user_id=None,
                idempotency_key=f"auto:{session_row.id}:{session_row.current_overall_pick}",
                now=now,
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if user_for_response is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate auto-pick request.") from exc
    if user_for_response is None:
        session_row = _get_session_or_404(db, mock_draft_id)
        host_user = db.get(User, session_row.host_user_id or session_row.commissioner_user_id)
        if host_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock draft host not found.")
        user_for_response = host_user
    return get_room_state(db, mock_draft_id=mock_draft_id, current_user=user_for_response)


def build_history(db: Session, *, mock_draft_id: int, current_user: User) -> MockDraftHistoryRead:
    session_row = _get_session_or_404(db, mock_draft_id)
    _require_participant(db, session_row, current_user)
    return build_mock_draft_history(db, session_row)


def email_history(db: Session, *, mock_draft_id: int, current_user: User) -> MockDraftEmailHistoryResponse:
    session_row = _get_session_or_404(db, mock_draft_id, lock=True)
    _require_participant(db, session_row, current_user)
    if session_row.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mock draft is not complete.")
    history = build_mock_draft_history(db, session_row)
    email = (current_user.email or "").strip().lower()
    if not settings.resend_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Email provider is not configured. Copy or download the draft history instead.",
                "history": history.model_dump(mode="json"),
            },
        )
    now = _now()
    session_row.history_email_sent_at = now
    session_row.should_preserve_history = True
    session_row.expires_at = now + timedelta(days=settings.mock_draft_emailed_retention_days)
    db.add(session_row)
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="email_sent", created_by_user_id=current_user.id)
    db.commit()
    return MockDraftEmailHistoryResponse(sent=True, emails=[email], message="Draft history email queued.", history=history)


def reset_single_player_mock_draft(db: Session, *, mock_draft_id: int, current_user: User) -> MockDraftRoomRead:
    now = _now()
    try:
        with db.begin_nested():
            session_row = _get_session_or_404(db, mock_draft_id, lock=True)
            participant = _require_participant(db, session_row, current_user)
            if _mock_draft_mode(session_row) != "single_player":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only single-player mock drafts can be reset here.")
            if not participant.is_host and session_row.host_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Host access required.")

            (
                db.query(MockDraftPick)
                .filter((MockDraftPick.mock_draft_id == session_row.id) | (MockDraftPick.session_id == session_row.id))
                .delete(synchronize_session=False)
            )
            participant_rows = _participants_query(db, session_row.id).with_for_update().all()
            for row in participant_rows:
                row.auto_pick_count = 0
                row.left_at = None
                row.connection_status = "connected"
                row.last_seen_at = now
                row.draft_position = None
                db.add(row)
            db.flush()

            fill_empty_seats_with_bots(db, session_row=session_row, now=now)
            session_row.draft_order_locked = False
            session_row.is_locked = False
            randomize_draft_order_once(db, session_row=session_row)
            session_row.status = "intermission"
            session_row.round_count = _fixed_mock_round_count()
            session_row.roster_slots_json = FIXED_ROSTER_SLOTS.copy()
            session_row.current_overall_pick = 1
            session_row.intermission_started_at = now
            session_row.intermission_ends_at = now + timedelta(seconds=SINGLE_PLAYER_PRE_DRAFT_SECONDS)
            session_row.started_at = None
            session_row.completed_at = None
            session_row.history_email_sent_at = None
            session_row.should_preserve_history = False
            session_row.expires_at = None
            session_row.current_pick_started_at = None
            session_row.current_pick_expires_at = None
            db.add(session_row)
            log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="reset", created_by_user_id=current_user.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mock draft state changed; refresh and try again.") from exc
    return get_room_state(db, mock_draft_id=mock_draft_id, current_user=current_user)


def exit_mock_draft(db: Session, *, mock_draft_id: int, current_user: User) -> MockDraftExitResponse:
    session_row = _get_session_or_404(db, mock_draft_id)
    participant = _require_participant(db, session_row, current_user)
    participant.left_at = _now()
    participant.connection_status = "disconnected"
    db.add(participant)
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="participant_left", created_by_user_id=current_user.id)
    db.commit()
    return MockDraftExitResponse(ok=True, navigate_to="/draft")


def recent_mock_drafts(db: Session, *, current_user: User) -> list[MockDraftSession]:
    return (
        db.query(MockDraftSession)
        .join(MockDraftParticipant, MockDraftParticipant.mock_draft_id == MockDraftSession.id)
        .filter(MockDraftParticipant.user_id == current_user.id, MockDraftSession.deleted_at.is_(None))
        .order_by(MockDraftSession.updated_at.desc())
        .limit(20)
        .all()
    )


def mark_for_auto_delete(db: Session, *, session_row: MockDraftSession, now: datetime | None = None) -> None:
    now = now or _now()
    session_row.status = "pending_deletion"
    session_row.expires_at = now
    db.add(session_row)
    log_mock_draft_event(db, mock_draft_id=session_row.id, event_type="marked_for_deletion")


def cleanup_expired_mock_drafts(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    now = now or _now()
    sessions = (
        db.query(MockDraftSession)
        .filter(
            MockDraftSession.status.in_(["completed", "cancelled", "expired", "pending_deletion"]),
            MockDraftSession.expires_at.is_not(None),
            MockDraftSession.expires_at < now,
            MockDraftSession.should_preserve_history.is_(False),
        )
        .all()
    )
    session_ids = [row.id for row in sessions]
    counts = {"sessions": len(session_ids), "picks": 0, "participants": 0, "events": 0}
    if not session_ids:
        return counts
    counts["picks"] = (
        db.query(MockDraftPick)
        .filter((MockDraftPick.mock_draft_id.in_(session_ids)) | (MockDraftPick.session_id.in_(session_ids)))
        .delete(synchronize_session=False)
    )
    counts["participants"] = (
        db.query(MockDraftParticipant)
        .filter(MockDraftParticipant.mock_draft_id.in_(session_ids))
        .delete(synchronize_session=False)
    )
    counts["events"] = (
        db.query(MockDraftEvent)
        .filter((MockDraftEvent.mock_draft_id.in_(session_ids)) | (MockDraftEvent.session_id.in_(session_ids)))
        .delete(synchronize_session=False)
    )
    for row in sessions:
        db.delete(row)
    db.flush()
    return counts
