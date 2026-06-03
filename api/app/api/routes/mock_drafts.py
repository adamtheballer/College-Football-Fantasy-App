from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import (
    JWTError,
    JWTExpiredError,
    generate_invite_code,
    verify_access_token,
)
from collegefootballfantasy_api.app.db.session import SessionLocal, get_db
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.models.mock_draft_event import MockDraftEvent
from collegefootballfantasy_api.app.models.mock_draft_lobby_member import MockDraftLobbyMember
from collegefootballfantasy_api.app.models.mock_draft_pick import MockDraftPick
from collegefootballfantasy_api.app.models.mock_draft_queue_item import MockDraftQueueItem
from collegefootballfantasy_api.app.models.mock_draft_roster import MockDraftRosterEntry
from collegefootballfantasy_api.app.models.mock_draft_seat import MockDraftSeat
from collegefootballfantasy_api.app.models.mock_draft_session import MockDraftSession
from collegefootballfantasy_api.app.models.mock_draft_timer_state import MockDraftTimerState
from collegefootballfantasy_api.app.schemas.draft_room import (
    DraftEventEnvelopeRead,
    DraftQueueItemRead,
    DraftRoomPickRead,
    DraftRoomTeamRead,
    DraftRosterPlayerRead,
    DraftRosterTeamRead,
)
from collegefootballfantasy_api.app.schemas.mock_draft import (
    MockDraftCreateRequest,
    MockDraftJoinByCodeRequest,
    MockDraftLobbyReadyRequest,
    MockDraftPreviewRead,
    MockDraftQueueAddRequest,
    MockDraftQueueRead,
    MockDraftQueueReorderRequest,
    MockDraftRoomRead,
    MockDraftRoomSnapshotRead,
    MockDraftSessionRead,
    MockDraftStatusUpdateRequest,
    MockDraftPickCreate,
)
from collegefootballfantasy_api.app.services.draft_realtime import draft_realtime_manager
from collegefootballfantasy_api.app.services.league_flow import FIXED_ROSTER_SLOTS
from collegefootballfantasy_api.app.services.mock_draft_event_stream import (
    append_mock_draft_event,
    latest_mock_draft_event_seq,
    list_mock_draft_events_since,
)
from collegefootballfantasy_api.app.api.routes.leagues import (
    DRAFT_CPU_AUTOPICK_BUFFER_SECONDS,
    DRAFT_LOBBY_CONNECTED_TTL_SECONDS,
    DRAFT_PICK_TRANSITION_SECONDS,
    DRAFT_POSITION_FULL_REASON,
    DRAFT_POSITION_LOCK_REASON,
    DRAFT_START_VISUAL_SECONDS,
    DRAFT_STATUS_MAP,
    EVENT_SCHEMA_VERSION,
    FLEX_BONUS,
    OFFENSE_DRAFT_POSITIONS,
    POSITION_DEMAND_BONUS,
    PROJECTION_WEIGHT,
    REPLACEMENT_RANK_BY_POSITION,
    VALUE_ABOVE_REPLACEMENT_WEIGHT,
    _draft_status_value,
    _draftable_roster_rounds_from_slots,
    can_draft_position,
)

router = APIRouter()

MOCK_DRAFT_TEAM_COUNTS = {4, 6, 8, 10, 12}
MOCK_DRAFT_STALE_TTL = timedelta(hours=24)
MOCK_DRAFT_SEAT_FILL_SECONDS = 120
MOCK_DRAFT_ROOM_PREVIEW_SECONDS = 120
MOCK_DRAFT_PUBLIC_INVITE_LENGTH = 20


def _mock_room_key(session_id: int) -> str:
    return f"mock:{session_id}"


def _event_legacy_name(event_type: str) -> str:
    mapping = {
        "draft.room.snapshot": "draft_room_ready",
        "draft.room.updated": "draft_room_updated",
        "draft.pick.made": "draft_pick_made",
    }
    return mapping.get(event_type, event_type.replace(".", "_"))


def _mock_mode(session_row: MockDraftSession) -> str:
    scoring_json = session_row.scoring_json or {}
    meta = scoring_json.get("__meta__") if isinstance(scoring_json, dict) else None
    mode = meta.get("mode") if isinstance(meta, dict) else None
    return str(mode or "public_multiplayer")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_user_from_ws_token(db: Session, token: str | None) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")
    try:
        payload = verify_access_token(token)
    except (JWTError, JWTExpiredError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid auth token") from exc
    user_id = int(payload.get("sub"))
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def _get_mock_draft_or_404(db: Session, session_id: int) -> MockDraftSession:
    row = db.get(MockDraftSession, session_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock draft not found")
    return row


def _require_mock_commissioner(db: Session, session_id: int, current_user: User) -> MockDraftSession:
    session_row = _get_mock_draft_or_404(db, session_id)
    if session_row.commissioner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner access required")
    return session_row


def _generate_unique_mock_invite(db: Session) -> str:
    for _ in range(20):
        code = generate_invite_code(MOCK_DRAFT_PUBLIC_INVITE_LENGTH)
        exists = db.query(MockDraftSession.id).filter(MockDraftSession.invite_code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="unable to generate invite code")


def _cleanup_stale_mock_drafts(db: Session) -> None:
    cutoff = datetime.now(timezone.utc) - MOCK_DRAFT_STALE_TTL
    stale_rows = (
        db.query(MockDraftSession)
        .filter(
            MockDraftSession.deleted_at.is_not(None)
            | (
                MockDraftSession.status.in_(("completed", "abandoned"))
                & (MockDraftSession.updated_at < cutoff)
            )
        )
        .limit(25)
        .all()
    )
    for row in stale_rows:
        db.delete(row)
    if stale_rows:
        db.flush()


def _ordered_mock_seats(db: Session, session_id: int) -> list[MockDraftSeat]:
    return (
        db.query(MockDraftSeat)
        .filter(MockDraftSeat.session_id == session_id)
        .order_by(MockDraftSeat.seat_number.asc(), MockDraftSeat.id.asc())
        .all()
    )


def _get_or_create_mock_timer_state(db: Session, session_id: int) -> MockDraftTimerState:
    row = (
        db.query(MockDraftTimerState)
        .filter(MockDraftTimerState.session_id == session_id)
        .with_for_update()
        .first()
    )
    if row is None:
        row = MockDraftTimerState(session_id=session_id)
        db.add(row)
        db.flush()
    return row


def _pause_draft_timer(*, timer_state: MockDraftTimerState, now_utc: datetime) -> None:
    if timer_state.paused_at is None:
        timer_state.paused_at = now_utc


def _start_or_resume_draft_timer(*, timer_state: MockDraftTimerState, now_utc: datetime) -> None:
    if timer_state.timer_started_at is None:
        timer_state.timer_started_at = now_utc
    if timer_state.paused_at is not None:
        paused_at = _as_utc(timer_state.paused_at) or now_utc
        timer_state.paused_total_seconds += max(0, int((now_utc - paused_at).total_seconds()))
        timer_state.paused_at = None


def _reset_draft_timer_for_next_pick(
    *,
    timer_state: MockDraftTimerState,
    now_utc: datetime,
    transition_seconds: int,
) -> None:
    timer_state.timer_started_at = now_utc + timedelta(seconds=max(0, int(transition_seconds)))
    timer_state.paused_at = None
    timer_state.paused_total_seconds = 0
    timer_state.last_tick_at = now_utc
    timer_state.auto_picking_started_at = None
    timer_state.auto_picking_pick_number = None
    timer_state.state_version = int(timer_state.state_version or 0) + 1


def _draft_pick_prep_remaining_seconds(
    *,
    session_row: MockDraftSession,
    timer_state: MockDraftTimerState | None,
    now_utc: datetime,
) -> int:
    if session_row.status != "live" or not timer_state or not timer_state.timer_started_at:
        return 0
    timer_started_at = _as_utc(timer_state.timer_started_at)
    if not timer_started_at:
        return 0
    return max(0, int(math.ceil((timer_started_at - now_utc).total_seconds())))


def _seconds_remaining_for_current_pick(
    *,
    session_row: MockDraftSession,
    timer_state: MockDraftTimerState | None,
    now_utc: datetime,
) -> int | None:
    if session_row.status not in {"scheduled", "countdown", "live", "paused"}:
        return None
    if session_row.status == "scheduled":
        start_at = _as_utc(session_row.draft_datetime_utc)
        if start_at is None:
            return None
        return max(0, int(math.ceil((start_at - now_utc).total_seconds())))
    if session_row.status == "countdown":
        timer_started_at = _as_utc(timer_state.timer_started_at) if timer_state else None
        anchor_started_at = timer_started_at or _as_utc(session_row.updated_at) or _as_utc(session_row.created_at)
        if not anchor_started_at:
            return MOCK_DRAFT_ROOM_PREVIEW_SECONDS
        elapsed_seconds = max(0, int((now_utc - anchor_started_at).total_seconds()))
        return max(0, int(MOCK_DRAFT_ROOM_PREVIEW_SECONDS) - elapsed_seconds)

    prep_remaining = _draft_pick_prep_remaining_seconds(
        session_row=session_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )
    pick_window_seconds = int(session_row.pick_timer_seconds)
    if prep_remaining > 0:
        return pick_window_seconds + prep_remaining
    timer_started_at = timer_state.timer_started_at if timer_state else None
    timer_paused_at = timer_state.paused_at if timer_state else None
    timer_paused_total_seconds = int(timer_state.paused_total_seconds if timer_state else 0)
    anchor_started_at = _as_utc(timer_started_at) or _as_utc(session_row.updated_at) or _as_utc(session_row.created_at)
    if not anchor_started_at:
        return None
    elapsed_until = now_utc
    if session_row.status == "paused" and timer_paused_at is not None:
        elapsed_until = _as_utc(timer_paused_at) or now_utc
    elapsed_seconds = max(
        0,
        int((elapsed_until - anchor_started_at).total_seconds()) - timer_paused_total_seconds,
    )
    return max(0, pick_window_seconds - elapsed_seconds)


def _draft_pick_seat_for_number(seats: list[MockDraftSeat], pick_number: int) -> tuple[int, int, MockDraftSeat | None]:
    if pick_number <= 0 or not seats:
        return 0, 0, None
    round_number = ((pick_number - 1) // len(seats)) + 1
    round_pick = ((pick_number - 1) % len(seats)) + 1
    round_order = seats if round_number % 2 == 1 else list(reversed(seats))
    return round_number, round_pick, round_order[round_pick - 1]


def _position_counts_for_roster_entries(
    roster_entries: list[tuple[MockDraftRosterEntry, Player]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _entry, player in roster_entries:
        counts[player.position] = counts.get(player.position, 0) + 1
    return counts


def _mock_rosters_by_seat(db: Session, session_id: int) -> list[DraftRosterTeamRead]:
    rows = (
        db.query(MockDraftRosterEntry, MockDraftSeat, Player)
        .join(MockDraftSeat, MockDraftSeat.id == MockDraftRosterEntry.seat_id)
        .join(Player, Player.id == MockDraftRosterEntry.player_id)
        .filter(MockDraftRosterEntry.session_id == session_id)
        .order_by(MockDraftSeat.seat_number.asc(), MockDraftRosterEntry.id.asc())
        .all()
    )
    by_seat: dict[int, list[tuple[MockDraftRosterEntry, Player]]] = {}
    seat_names: dict[int, str] = {}
    for entry, seat, player in rows:
        by_seat.setdefault(seat.id, []).append((entry, player))
        seat_names[seat.id] = seat.name

    payload: list[DraftRosterTeamRead] = []
    for seat_id, roster_rows in by_seat.items():
        slots: dict[str, list[DraftRosterPlayerRead]] = {}
        total_projected_points = 0.0
        for entry, player in roster_rows:
            projected = float(player.sheet_projected_season_points or 0.0)
            total_projected_points += projected
            slots.setdefault(entry.slot, []).append(
                DraftRosterPlayerRead(
                    player_id=player.id,
                    player_name=player.name,
                    position=player.position,
                    school=player.school,
                    slot=entry.slot,
                    projected_fantasy_points=projected if player.sheet_projected_season_points is not None else None,
                )
            )
        payload.append(
            DraftRosterTeamRead(
                team_id=seat_id,
                team_name=seat_names.get(seat_id, f"Seat {seat_id}"),
                total_projected_points=round(total_projected_points, 2),
                position_counts=_position_counts_for_roster_entries(roster_rows),
                slots=slots,
            )
        )
    return payload


def _mock_lobby_presence_summary(
    db: Session,
    *,
    session_id: int,
    seats: list[MockDraftSeat],
    now_utc: datetime,
) -> tuple[dict[int, dict[str, bool]], int, int, int]:
    rows = (
        db.query(MockDraftLobbyMember)
        .filter(MockDraftLobbyMember.session_id == session_id)
        .all()
    )
    connected_cutoff = now_utc - timedelta(seconds=DRAFT_LOBBY_CONNECTED_TTL_SECONDS)
    by_seat: dict[int, dict[str, bool]] = {
        seat.id: {
            "joined": seat.owner_user_id is not None or seat.is_cpu,
            "connected": seat.is_cpu,
            "ready": seat.is_cpu,
        }
        for seat in seats
    }
    joined_count = sum(1 for seat in seats if seat.owner_user_id is not None or seat.is_cpu)
    connected_count = sum(1 for seat in seats if seat.is_cpu)
    ready_count = sum(1 for seat in seats if seat.is_cpu)
    for row in rows:
        flags = by_seat.get(row.seat_id)
        if flags is None:
            continue
        last_seen = _as_utc(row.last_seen_at)
        connected = bool(last_seen and last_seen >= connected_cutoff)
        ready = bool(row.is_ready)
        if not flags["connected"] and connected:
            connected_count += 1
        if not flags["ready"] and ready:
            ready_count += 1
        flags["connected"] = flags["connected"] or connected
        flags["ready"] = flags["ready"] or ready
    return by_seat, joined_count, connected_count, ready_count


def _upsert_mock_lobby_member(
    db: Session,
    *,
    session_id: int,
    seat_id: int,
    user_id: int,
    set_ready: bool | None = None,
) -> MockDraftLobbyMember:
    row = (
        db.query(MockDraftLobbyMember)
        .filter(
            MockDraftLobbyMember.session_id == session_id,
            MockDraftLobbyMember.user_id == user_id,
        )
        .with_for_update()
        .first()
    )
    now_utc = datetime.now(timezone.utc)
    if row is None:
        row = MockDraftLobbyMember(
            session_id=session_id,
            seat_id=seat_id,
            user_id=user_id,
            joined_at=now_utc,
            last_seen_at=now_utc,
            is_ready=bool(set_ready) if set_ready is not None else False,
        )
        db.add(row)
        db.flush()
        return row
    row.seat_id = seat_id
    row.last_seen_at = now_utc
    if set_ready is not None:
        row.is_ready = bool(set_ready)
    db.add(row)
    db.flush()
    return row


def _resolve_user_mock_seat(
    db: Session,
    *,
    session_row: MockDraftSession,
    current_user: User,
) -> MockDraftSeat:
    owned = (
        db.query(MockDraftSeat)
        .filter(
            MockDraftSeat.session_id == session_row.id,
            MockDraftSeat.owner_user_id == current_user.id,
        )
        .with_for_update()
        .first()
    )
    if owned is not None:
        return owned
    open_seat = (
        db.query(MockDraftSeat)
        .filter(
            MockDraftSeat.session_id == session_row.id,
            MockDraftSeat.owner_user_id.is_(None),
            MockDraftSeat.is_cpu.is_(False),
        )
        .order_by(MockDraftSeat.seat_number.asc())
        .with_for_update()
        .first()
    )
    if open_seat is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mock draft is full")
    display_name = (current_user.first_name or "").strip() or (current_user.email or "Manager").split("@")[0]
    open_seat.owner_user_id = current_user.id
    open_seat.owner_name = display_name
    open_seat.name = f"{display_name}'s Team"
    db.add(open_seat)
    db.flush()
    return open_seat


def _mock_room_event_envelope(event_row: MockDraftEvent) -> DraftEventEnvelopeRead:
    return DraftEventEnvelopeRead(
        event_id=f"evt_{event_row.id}",
        event=_event_legacy_name(event_row.event_type),
        event_type=event_row.event_type,
        league_id=0,
        entity_type=event_row.entity_type,
        entity_id=event_row.entity_id,
        seq=event_row.id,
        schema_version=event_row.schema_version,
        at=event_row.occurred_at,
        payload={**(event_row.payload or {}), "mock_draft_id": event_row.session_id},
    )


def _broadcast_mock_draft_event(room_key: str, envelope: DraftEventEnvelopeRead) -> None:
    async def _run() -> None:
        await draft_realtime_manager.broadcast(
            room_key,
            event=envelope.event,
            payload=envelope.payload,
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            seq=envelope.seq,
            schema_version=envelope.schema_version,
            entity_type=envelope.entity_type,
            entity_id=envelope.entity_id,
            occurred_at=envelope.at,
        )

    try:
        asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()


def _emit_mock_draft_event(
    db: Session,
    *,
    session_id: int,
    event_type: str,
    payload: dict | None = None,
    entity_type: str = "mock_draft",
    entity_id: int | None = None,
) -> DraftEventEnvelopeRead:
    row = append_mock_draft_event(
        db,
        session_id=session_id,
        event_type=event_type,
        payload=payload or {},
        entity_type=entity_type,
        entity_id=entity_id,
        schema_version=EVENT_SCHEMA_VERSION,
    )
    envelope = _mock_room_event_envelope(row)
    _broadcast_mock_draft_event(_mock_room_key(session_id), envelope)
    return envelope


def _total_rounds_for_session(session_row: MockDraftSession) -> int:
    return max(1, _draftable_roster_rounds_from_slots(session_row.roster_slots_json or FIXED_ROSTER_SLOTS))


def _total_picks_for_session(session_row: MockDraftSession) -> int:
    return _total_rounds_for_session(session_row) * int(session_row.manager_count)


def _current_room_eligibility(
    roster_entries: list[MockDraftRosterEntry],
    session_row: MockDraftSession,
) -> dict[str, dict[str, str | bool | None]]:
    payload: dict[str, dict[str, str | bool | None]] = {}
    for position in ("QB", "RB", "WR", "TE", "K"):
        fit = can_draft_position(position, roster_entries, session_row.roster_slots_json or FIXED_ROSTER_SLOTS)
        reason = fit.reason
        if reason == DRAFT_POSITION_FULL_REASON:
            reason = DRAFT_POSITION_LOCK_REASON
        payload[position] = {
            "can_draft": fit.can_draft,
            "reason": reason,
            "destination_slot": fit.destination_slot,
        }
    return payload


def _mock_room_state(db: Session, session_row: MockDraftSession, current_user: User) -> MockDraftRoomRead:
    seats = _ordered_mock_seats(db, session_row.id)
    picks_rows = (
        db.query(MockDraftPick, MockDraftSeat, Player)
        .join(MockDraftSeat, MockDraftSeat.id == MockDraftPick.seat_id)
        .join(Player, Player.id == MockDraftPick.player_id)
        .filter(MockDraftPick.session_id == session_row.id)
        .order_by(MockDraftPick.overall_pick.asc())
        .all()
    )
    drafted_player_ids = [player.id for _pick, _seat, player in picks_rows]
    total_rounds = _total_rounds_for_session(session_row)
    total_picks = _total_picks_for_session(session_row)
    current_pick = len(picks_rows) + 1
    current_round, current_round_pick, current_seat = _draft_pick_seat_for_number(seats, current_pick)
    if total_picks and len(picks_rows) >= total_picks:
        current_seat = None

    roster_entries_by_seat: dict[int, list[MockDraftRosterEntry]] = {}
    roster_rows = (
        db.query(MockDraftRosterEntry)
        .filter(MockDraftRosterEntry.session_id == session_row.id)
        .all()
    )
    for row in roster_rows:
        roster_entries_by_seat.setdefault(row.seat_id, []).append(row)

    current_roster_entries = roster_entries_by_seat.get(current_seat.id, []) if current_seat else []
    position_eligibility = (
        _current_room_eligibility(current_roster_entries, session_row)
        if current_seat
        else {}
    )
    timer_state = (
        db.query(MockDraftTimerState)
        .filter(MockDraftTimerState.session_id == session_row.id)
        .first()
    )
    timer_started_at = timer_state.timer_started_at if timer_state else None
    timer_paused_at = timer_state.paused_at if timer_state else None
    timer_paused_total_seconds = int(timer_state.paused_total_seconds if timer_state else 0)
    now_utc = datetime.now(timezone.utc)
    prep_remaining = _draft_pick_prep_remaining_seconds(
        session_row=session_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )
    seconds_remaining = _seconds_remaining_for_current_pick(
        session_row=session_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )
    current_pick_expires_at: datetime | None = None
    if seconds_remaining is not None and session_row.status != "paused" and current_seat is not None:
        current_pick_expires_at = now_utc + timedelta(seconds=seconds_remaining)

    lobby_presence_by_seat, joined_count, connected_count, ready_count = _mock_lobby_presence_summary(
        db,
        session_id=session_row.id,
        seats=seats,
        now_utc=now_utc,
    )
    user_seat = next((seat for seat in seats if seat.owner_user_id == current_user.id), None)
    has_time_remaining = seconds_remaining is None or seconds_remaining > 0
    can_make_pick = bool(
        session_row.status == "live"
        and current_seat is not None
        and prep_remaining <= 0
        and has_time_remaining
        and current_seat.owner_user_id == current_user.id
    )

    phase_type: str | None = None
    phase_seconds_remaining: int | None = None
    if session_row.status == "scheduled":
        phase_type = "lobby_countdown"
        phase_seconds_remaining = seconds_remaining
    elif session_row.status == "countdown":
        phase_type = "prestart_countdown"
        phase_seconds_remaining = seconds_remaining
    elif session_row.status in {"live", "paused"}:
        if prep_remaining > 0:
            phase_type = "pick_transition"
            phase_seconds_remaining = prep_remaining
        else:
            phase_type = "pick_clock"
            phase_seconds_remaining = seconds_remaining

    server_state_seq = latest_mock_draft_event_seq(db, session_id=session_row.id)
    available_player_count = (
        db.query(func.count(Player.id))
        .filter(Player.position.in_(tuple(OFFENSE_DRAFT_POSITIONS)))
        .filter(~Player.id.in_(db.query(MockDraftPick.player_id).filter(MockDraftPick.session_id == session_row.id)))
        .scalar()
        or 0
    )
    return MockDraftRoomRead(
        draft_room_id=session_row.id,
        mock_draft_id=session_row.id,
        mode=_mock_mode(session_row),        
        status=session_row.status,
        draft_status=_draft_status_value(session_row.status),
        pick_timer_seconds=session_row.pick_timer_seconds,
        total_rounds=total_rounds,
        total_picks=total_picks,
        roster_slots=session_row.roster_slots_json or FIXED_ROSTER_SLOTS,
        position_eligibility=position_eligibility,
        draft_order=[seat.id for seat in seats],
        drafted_player_ids=drafted_player_ids,
        available_player_count=int(available_player_count),
        rosters_by_team=_mock_rosters_by_seat(db, session_row.id),
        lobby_ready_count=ready_count,
        lobby_joined_count=joined_count,
        lobby_connected_count=connected_count,
        teams=[
            DraftRoomTeamRead(
                id=seat.id,
                name=seat.name,
                owner_user_id=seat.owner_user_id,
                owner_name=seat.owner_name,
                lobby_joined=bool(lobby_presence_by_seat.get(seat.id, {}).get("joined")),
                lobby_connected=bool(lobby_presence_by_seat.get(seat.id, {}).get("connected")),
                lobby_ready=bool(lobby_presence_by_seat.get(seat.id, {}).get("ready")),
            )
            for seat in seats
        ],
        picks=[
            DraftRoomPickRead(
                id=pick.id,
                overall_pick=pick.overall_pick,
                round_number=pick.round_number,
                round_pick=pick.round_pick,
                team_id=seat.id,
                team_name=seat.name,
                player_id=player.id,
                player_name=player.name,
                player_position=player.position,
                player_school=player.school,
                made_by_user_id=pick.made_by_user_id,
                created_at=pick.created_at,
            )
            for pick, seat, player in picks_rows
        ],
        current_pick=current_pick,
        current_round=current_round,
        current_round_pick=current_round_pick,
        current_team_id=current_seat.id if current_seat else None,
        current_team_name=current_seat.name if current_seat else None,
        current_pick_expires_at=current_pick_expires_at,
        seconds_remaining=seconds_remaining,
        phase_seconds_remaining=phase_seconds_remaining,
        phase_type=phase_type,
        pick_state="PICK_SUBMITTED" if phase_type == "pick_transition" else "WAITING_FOR_PICK",
        auto_pick_seconds_remaining=None,
        current_pick_timer_seconds=int(session_row.pick_timer_seconds),
        timer_started_at=timer_started_at,
        timer_paused_at=timer_paused_at,
        timer_paused_total_seconds=timer_paused_total_seconds,
        server_state_seq=server_state_seq,
        user_team_id=user_seat.id if user_seat else None,
        can_make_pick=can_make_pick,
        created_at=session_row.created_at,
        updated_at=session_row.updated_at,
    )


def _ordered_autopick_candidates(db: Session, *, session_id: int, limit: int = 300) -> list[Player]:
    drafted_subquery = db.query(MockDraftPick.player_id).filter(MockDraftPick.session_id == session_id)
    rostered_subquery = db.query(MockDraftRosterEntry.player_id).filter(MockDraftRosterEntry.session_id == session_id)
    adp_missing = case((Player.sheet_adp.is_(None), 1), else_=0)
    adp_non_positive = case((Player.sheet_adp <= 0, 1), else_=0)
    latest_projection_window = (
        db.query(WeeklyProjection.season, WeeklyProjection.week)
        .order_by(WeeklyProjection.season.desc(), WeeklyProjection.week.desc())
        .first()
    )
    query = (
        db.query(Player)
        .filter(Player.position.in_(tuple(OFFENSE_DRAFT_POSITIONS)))
        .filter(~Player.id.in_(drafted_subquery))
        .filter(~Player.id.in_(rostered_subquery))
    )
    if latest_projection_window:
        sheet_projection_points = func.coalesce(Player.sheet_projected_season_points, -1.0)
        projection_points = func.coalesce(WeeklyProjection.fantasy_points, 0.0)
        query = (
            query
            .outerjoin(
                WeeklyProjection,
                and_(
                    WeeklyProjection.player_id == Player.id,
                    WeeklyProjection.season == int(latest_projection_window[0]),
                    WeeklyProjection.week == int(latest_projection_window[1]),
                ),
            )
            .order_by(
                adp_missing.asc(),
                adp_non_positive.asc(),
                Player.sheet_adp.asc(),
                sheet_projection_points.desc(),
                projection_points.desc(),
                Player.id.asc(),
            )
        )
    else:
        sheet_projection_points = func.coalesce(Player.sheet_projected_season_points, -1.0)
        query = query.order_by(
            adp_missing.asc(),
            adp_non_positive.asc(),
            Player.sheet_adp.asc(),
            sheet_projection_points.desc(),
            Player.id.asc(),
        )
    return query.limit(limit).all()


def _normalize_queue_priorities(db: Session, *, session_id: int, seat_id: int) -> list[MockDraftQueueItem]:
    rows = (
        db.query(MockDraftQueueItem)
        .filter(MockDraftQueueItem.session_id == session_id, MockDraftQueueItem.seat_id == seat_id)
        .order_by(MockDraftQueueItem.priority.asc(), MockDraftQueueItem.id.asc())
        .all()
    )
    changed = False
    for index, row in enumerate(rows, start=1):
        if int(row.priority) != index:
            row.priority = index
            db.add(row)
            changed = True
    if changed:
        db.flush()
    return rows


def _remove_player_from_mock_queues(db: Session, *, session_id: int, player_id: int) -> None:
    (
        db.query(MockDraftQueueItem)
        .filter(MockDraftQueueItem.session_id == session_id, MockDraftQueueItem.player_id == player_id)
        .delete(synchronize_session=False)
    )
    db.flush()


def _queued_autopick_candidate(db: Session, *, session_id: int, seat_id: int) -> Player | None:
    drafted_subquery = db.query(MockDraftPick.player_id).filter(MockDraftPick.session_id == session_id)
    rostered_subquery = db.query(MockDraftRosterEntry.player_id).filter(MockDraftRosterEntry.session_id == session_id)
    queue_rows = _normalize_queue_priorities(db, session_id=session_id, seat_id=seat_id)
    for queue_row in queue_rows:
        player = (
            db.query(Player)
            .filter(Player.id == queue_row.player_id)
            .filter(~Player.id.in_(drafted_subquery))
            .filter(~Player.id.in_(rostered_subquery))
            .first()
        )
        if player:
            return player
    return None


def _draft_queue_state(db: Session, *, session_row: MockDraftSession, seat_id: int) -> MockDraftQueueRead:
    queue_rows = _normalize_queue_priorities(db, session_id=session_row.id, seat_id=seat_id)
    data: list[DraftQueueItemRead] = []
    removed_any = False
    for row in queue_rows:
        player = db.get(Player, row.player_id)
        if player is None:
            db.delete(row)
            removed_any = True
            continue
        drafted = (
            db.query(MockDraftPick.id)
            .filter(MockDraftPick.session_id == session_row.id, MockDraftPick.player_id == player.id)
            .first()
        )
        rostered = (
            db.query(MockDraftRosterEntry.id)
            .filter(MockDraftRosterEntry.session_id == session_row.id, MockDraftRosterEntry.player_id == player.id)
            .first()
        )
        if drafted or rostered:
            db.delete(row)
            removed_any = True
            continue
        data.append(
            DraftQueueItemRead(
                id=row.id,
                priority=int(row.priority),
                player_id=player.id,
                player_name=player.name,
                player_position=player.position,
                player_school=player.school,
                player_class=player.player_class,
                projected_fantasy_points=float(player.sheet_projected_season_points)
                if player.sheet_projected_season_points is not None
                else None,
                adp=float(player.sheet_adp) if player.sheet_adp is not None else None,
            )
        )
    if removed_any:
        db.flush()
    return MockDraftQueueRead(session_id=session_row.id, seat_id=seat_id, count=len(data), data=data)


def _seat_pre_draft_score(
    db: Session,
    *,
    session_row: MockDraftSession,
    seat_id: int,
) -> float:
    picks_made = db.query(MockDraftPick.id).filter(MockDraftPick.seat_id == seat_id).count()
    if picks_made:
        return -1_000_000.0
    player_rows = (
        db.query(Player)
        .filter(Player.position.in_(tuple(OFFENSE_DRAFT_POSITIONS)))
        .limit(250)
        .all()
    )
    score = 0.0
    for player in player_rows:
        position = (player.position or "").upper()
        projection = float(player.sheet_projected_season_points or 0.0)
        adp = float(player.sheet_adp or 999.0)
        replacement_rank = REPLACEMENT_RANK_BY_POSITION.get(position, 24)
        replacement_penalty = max(0.0, adp - replacement_rank)
        score += (
            (projection * PROJECTION_WEIGHT)
            + POSITION_DEMAND_BONUS.get(position, 0)
            + FLEX_BONUS.get(position, 0)
            - (replacement_penalty * VALUE_ABOVE_REPLACEMENT_WEIGHT)
        )
    return round(score, 4)


def _apply_random_draft_order(db: Session, *, session_row: MockDraftSession) -> None:
    seats = _ordered_mock_seats(db, session_row.id)
    ranked = sorted(
        ((seat, _seat_pre_draft_score(db, session_row=session_row, seat_id=seat.id)) for seat in seats),
        key=lambda item: item[1],
        reverse=True,
    )
    for index, (seat, _score) in enumerate(ranked, start=1):
        seat.seat_number = index
        db.add(seat)
    db.flush()


def _assign_cpu_seats(db: Session, *, session_row: MockDraftSession) -> None:
    seats = _ordered_mock_seats(db, session_row.id)
    for seat in seats:
        if seat.owner_user_id is not None:
            continue
        seat.is_cpu = True
        seat.owner_name = "CPU"
        seat.name = f"CPU {seat.seat_number}"
        db.add(seat)
    db.flush()


def _advance_scheduled_to_countdown(
    db: Session,
    *,
    session_row: MockDraftSession,
    timer_state: MockDraftTimerState,
    now_utc: datetime,
) -> bool:
    if session_row.status != "scheduled":
        return False
    start_at = _as_utc(session_row.draft_datetime_utc)
    if start_at is None or start_at > now_utc:
        return False
    _assign_cpu_seats(db, session_row=session_row)
    _apply_random_draft_order(db, session_row=session_row)
    session_row.status = "countdown"
    _reset_draft_timer_for_next_pick(
        timer_state=timer_state,
        now_utc=now_utc,
        transition_seconds=0,
    )
    db.add(session_row)
    db.add(timer_state)
    return True


def _advance_countdown_if_ready(
    db: Session,
    *,
    session_row: MockDraftSession,
    timer_state: MockDraftTimerState,
    now_utc: datetime,
) -> bool:
    if session_row.status != "countdown":
        return False
    seconds_remaining = _seconds_remaining_for_current_pick(
        session_row=session_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )
    if seconds_remaining is None or seconds_remaining > 0:
        return False
    session_row.status = "live"
    _reset_draft_timer_for_next_pick(
        timer_state=timer_state,
        now_utc=now_utc,
        transition_seconds=DRAFT_START_VISUAL_SECONDS,
    )
    db.add(session_row)
    db.add(timer_state)
    return True


def _autopick_timed_out_current_seat(db: Session, *, session_row: MockDraftSession) -> bool:
    now_utc = datetime.now(timezone.utc)
    changed = False
    with db.begin_nested():
        session_row = (
            db.query(MockDraftSession)
            .filter(MockDraftSession.id == session_row.id)
            .with_for_update()
            .first()
        )
        if session_row is None:
            return False
        timer_state = _get_or_create_mock_timer_state(db, session_row.id)
        seats = _ordered_mock_seats(db, session_row.id)
        if _advance_scheduled_to_countdown(
            db,
            session_row=session_row,
            timer_state=timer_state,
            now_utc=now_utc,
        ):
            changed = True
            return changed
        if _advance_countdown_if_ready(
            db,
            session_row=session_row,
            timer_state=timer_state,
            now_utc=now_utc,
        ):
            changed = True
            return changed
        if session_row.status != "live":
            return False
        total_picks = _total_picks_for_session(session_row)
        existing_picks = db.query(MockDraftPick).filter(MockDraftPick.session_id == session_row.id).count()
        if total_picks and existing_picks >= total_picks:
            session_row.status = "completed"
            session_row.completed_at = now_utc
            db.add(session_row)
            return True
        round_number, round_pick, current_seat = _draft_pick_seat_for_number(seats, existing_picks + 1)
        if current_seat is None:
            return False
        seconds_remaining = _seconds_remaining_for_current_pick(
            session_row=session_row,
            timer_state=timer_state,
            now_utc=now_utc,
        )
        if seconds_remaining is None:
            return False
        autopick_trigger_seconds = 0
        if current_seat.owner_user_id is None or current_seat.is_cpu:
            autopick_trigger_seconds = max(
                0,
                int(session_row.pick_timer_seconds) - int(DRAFT_CPU_AUTOPICK_BUFFER_SECONDS),
            )
        if seconds_remaining > autopick_trigger_seconds:
            return False
        current_pick_number = existing_picks + 1
        pick_idempotency = f"timeout:mock:{session_row.id}:{current_pick_number}"
        existing_timeout_pick = (
            db.query(MockDraftPick)
            .filter(MockDraftPick.session_id == session_row.id, MockDraftPick.idempotency_key == pick_idempotency)
            .first()
        )
        if existing_timeout_pick:
            return False
        selected_player = _queued_autopick_candidate(db, session_id=session_row.id, seat_id=current_seat.id)
        selected_slot: str | None = None
        current_roster = (
            db.query(MockDraftRosterEntry)
            .filter(MockDraftRosterEntry.seat_id == current_seat.id)
            .all()
        )
        if selected_player is not None:
            fit = can_draft_position(selected_player.position, current_roster, session_row.roster_slots_json)
            if fit.can_draft and fit.destination_slot:
                selected_slot = fit.destination_slot
            else:
                selected_player = None
        if selected_player is None:
            for candidate in _ordered_autopick_candidates(db, session_id=session_row.id):
                fit = can_draft_position(candidate.position, current_roster, session_row.roster_slots_json)
                if not fit.can_draft or not fit.destination_slot:
                    continue
                selected_player = candidate
                selected_slot = fit.destination_slot
                break
        if selected_player is None or selected_slot is None:
            return False
        db.add(
            MockDraftPick(
                session_id=session_row.id,
                seat_id=current_seat.id,
                player_id=selected_player.id,
                made_by_user_id=None,
                round_number=round_number,
                round_pick=round_pick,
                overall_pick=current_pick_number,
                idempotency_key=pick_idempotency,
            )
        )
        db.flush()
        db.add(
            MockDraftRosterEntry(
                session_id=session_row.id,
                seat_id=current_seat.id,
                player_id=selected_player.id,
                slot=selected_slot,
                status="active",
            )
        )
        db.flush()
        _remove_player_from_mock_queues(db, session_id=session_row.id, player_id=selected_player.id)
        _reset_draft_timer_for_next_pick(
            timer_state=timer_state,
            now_utc=now_utc,
            transition_seconds=DRAFT_PICK_TRANSITION_SECONDS,
        )
        if total_picks and current_pick_number >= total_picks:
            session_row.status = "completed"
            session_row.completed_at = now_utc
            timer_state.paused_at = now_utc
        db.add(session_row)
        db.add(timer_state)
        changed = True
    if changed:
        db.commit()
        _emit_mock_draft_event(
            db,
            session_id=session_row.id,
            event_type="draft.pick.made",
            entity_type="draft_room",
            entity_id=session_row.id,
            payload={"reason": "timeout_autopick"},
        )
        db.commit()
    return changed


@router.post("", response_model=MockDraftSessionRead)
def create_mock_draft(
    payload: MockDraftCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftSessionRead:
    _cleanup_stale_mock_drafts(db)
    invite_code = _generate_unique_mock_invite(db)
    session_row = MockDraftSession(
        commissioner_user_id=current_user.id,
        invite_code=invite_code,
        name=payload.name.strip() or "Mock Draft",
        status="countdown" if payload.mode == "single_player" else "scheduled",
        manager_count=payload.manager_count,
        draft_type="snake",
        pick_timer_seconds=payload.pick_timer_seconds,
        roster_slots_json=FIXED_ROSTER_SLOTS.copy(),
        scoring_json={"preset": "espn_full_ppr", "__meta__": {"mock": True, "mode": payload.mode}},
        draft_datetime_utc=(
            datetime.now(timezone.utc)
            if payload.mode == "single_player"
            else datetime.now(timezone.utc) + timedelta(seconds=MOCK_DRAFT_SEAT_FILL_SECONDS)
        ),
    )
    db.add(session_row)
    db.flush()
    db.add(MockDraftTimerState(session_id=session_row.id))
    for seat_number in range(1, payload.manager_count + 1):
        db.add(
            MockDraftSeat(
                session_id=session_row.id,
                seat_number=seat_number,
                name=f"Open Seat {seat_number}",
                owner_name=None,
                owner_user_id=None,
                is_cpu=False,
            )
        )
    db.flush()
    commissioner_seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
    _upsert_mock_lobby_member(
        db,
        session_id=session_row.id,
        seat_id=commissioner_seat.id,
        user_id=current_user.id,
        set_ready=False,
    )
    if payload.mode == "single_player":
        timer_state = _get_or_create_mock_timer_state(db, session_row.id)
        _assign_cpu_seats(db, session_row=session_row)
        _apply_random_draft_order(db, session_row=session_row)
        _reset_draft_timer_for_next_pick(
            timer_state=timer_state,
            now_utc=datetime.now(timezone.utc),
            transition_seconds=0,
        )
        db.add(timer_state)
    db.commit()
    db.refresh(session_row)
    return get_mock_draft_lobby(session_row.id, db, current_user)


@router.post("/join-by-code", response_model=MockDraftPreviewRead)
def preview_mock_draft_by_code(
    payload: MockDraftJoinByCodeRequest,
    db: Session = Depends(get_db),
) -> MockDraftPreviewRead:
    _cleanup_stale_mock_drafts(db)
    session_row = (
        db.query(MockDraftSession)
        .filter(MockDraftSession.invite_code == payload.invite_code.upper(), MockDraftSession.deleted_at.is_(None))
        .first()
    )
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock draft invite code not found")
    if _mock_mode(session_row) != "public_multiplayer":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mock draft is not joinable by invite code")
    joined_count = (
        db.query(MockDraftSeat.id)
        .filter(MockDraftSeat.session_id == session_row.id)
        .filter((MockDraftSeat.owner_user_id.is_not(None)) | (MockDraftSeat.is_cpu.is_(True)))
        .count()
    )
    return MockDraftPreviewRead(
        id=session_row.id,
        name=session_row.name,
        invite_code=session_row.invite_code,
        mode=_mock_mode(session_row),
        status=session_row.status,
        manager_count=session_row.manager_count,
        joined_count=joined_count,
        pick_timer_seconds=session_row.pick_timer_seconds,
    )


@router.post("/join-with-code", response_model=MockDraftSessionRead)
def join_mock_draft_by_code(
    payload: MockDraftJoinByCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftSessionRead:
    _cleanup_stale_mock_drafts(db)
    session_row = (
        db.query(MockDraftSession)
        .filter(MockDraftSession.invite_code == payload.invite_code.upper(), MockDraftSession.deleted_at.is_(None))
        .with_for_update()
        .first()
    )
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock draft invite code not found")
    if _mock_mode(session_row) != "public_multiplayer":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mock draft is not joinable by invite code")
    if session_row.status in {"completed", "abandoned", "countdown", "live", "paused"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mock draft is no longer joinable")
    seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
    _upsert_mock_lobby_member(
        db,
        session_id=session_row.id,
        seat_id=seat.id,
        user_id=current_user.id,
        set_ready=False,
    )
    _emit_mock_draft_event(
        db,
        session_id=session_row.id,
        event_type="draft.lobby.updated",
        entity_type="draft_room",
        entity_id=session_row.id,
        payload={"action": "join", "seat_id": seat.id, "user_id": current_user.id},
    )
    db.commit()
    return get_mock_draft_lobby(session_row.id, db, current_user)


@router.get("/{session_id}/lobby", response_model=MockDraftSessionRead)
def get_mock_draft_lobby(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftSessionRead:
    session_row = (
        db.query(MockDraftSession)
        .filter(MockDraftSession.id == session_id)
        .with_for_update()
        .first()
    )
    if session_row is None or session_row.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock draft not found")
    timer_state = _get_or_create_mock_timer_state(db, session_id)
    now_utc = datetime.now(timezone.utc)
    advanced = _advance_scheduled_to_countdown(
        db,
        session_row=session_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )
    if advanced:
        _emit_mock_draft_event(
            db,
            session_id=session_id,
            event_type="draft.status.changed",
            entity_type="draft_room",
            entity_id=session_id,
            payload={"status": session_row.status, "reason": "seat_fill_timer_complete"},
        )
        db.commit()
        db.refresh(session_row)
    seats = _ordered_mock_seats(db, session_id)
    presence_by_seat, joined_count, connected_count, ready_count = _mock_lobby_presence_summary(
        db,
        session_id=session_id,
        seats=seats,
        now_utc=now_utc,
    )
    user_seat = next((seat for seat in seats if seat.owner_user_id == current_user.id), None)
    seconds_remaining: int | None = None
    if session_row.status == "scheduled":
        start_at = _as_utc(session_row.draft_datetime_utc)
        if start_at is not None:
            seconds_remaining = max(0, int(math.ceil((start_at - now_utc).total_seconds())))
    elif session_row.status == "countdown":
        seconds_remaining = _seconds_remaining_for_current_pick(
            session_row=session_row,
            timer_state=timer_state,
            now_utc=now_utc,
        )
    return MockDraftSessionRead(
        id=session_row.id,
        name=session_row.name,
        invite_code=session_row.invite_code,
        mode=_mock_mode(session_row),
        status=session_row.status,
        manager_count=session_row.manager_count,
        pick_timer_seconds=session_row.pick_timer_seconds,
        draft_type=session_row.draft_type,
        commissioner_user_id=session_row.commissioner_user_id,
        roster_slots=session_row.roster_slots_json or FIXED_ROSTER_SLOTS,
        scoring_json=session_row.scoring_json or {},
        seats=[
            {
                "id": seat.id,
                "seat_number": seat.seat_number,
                "name": seat.name,
                "owner_name": seat.owner_name,
                "owner_user_id": seat.owner_user_id,
                "is_cpu": seat.is_cpu,
                "lobby_joined": bool(presence_by_seat.get(seat.id, {}).get("joined")),
                "lobby_connected": bool(presence_by_seat.get(seat.id, {}).get("connected")),
                "lobby_ready": bool(presence_by_seat.get(seat.id, {}).get("ready")),
            }
            for seat in seats
        ],
        joined_count=joined_count,
        connected_count=connected_count,
        ready_count=ready_count,
        user_seat_id=user_seat.id if user_seat else None,
        seconds_remaining=seconds_remaining,
        can_enter_room=session_row.status in {"countdown", "live", "paused"},
        created_at=session_row.created_at,
        updated_at=session_row.updated_at,
    )


@router.post("/{session_id}/lobby/join", response_model=MockDraftSessionRead)
def join_mock_draft_lobby(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftSessionRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    if _mock_mode(session_row) != "public_multiplayer":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="single-player mock drafts do not accept lobby joins")
    if session_row.status in {"countdown", "live", "paused", "completed", "abandoned"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mock lobby is closed")
    seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
    _upsert_mock_lobby_member(db, session_id=session_id, seat_id=seat.id, user_id=current_user.id, set_ready=None)
    _emit_mock_draft_event(
        db,
        session_id=session_id,
        event_type="draft.lobby.updated",
        entity_type="draft_room",
        entity_id=session_id,
        payload={"action": "join", "seat_id": seat.id, "user_id": current_user.id},
    )
    db.commit()
    return get_mock_draft_lobby(session_id, db, current_user)


@router.post("/{session_id}/lobby/ready", response_model=MockDraftSessionRead)
def set_mock_draft_ready(
    session_id: int,
    payload: MockDraftLobbyReadyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftSessionRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
    _upsert_mock_lobby_member(
        db,
        session_id=session_id,
        seat_id=seat.id,
        user_id=current_user.id,
        set_ready=payload.ready,
    )
    _emit_mock_draft_event(
        db,
        session_id=session_id,
        event_type="draft.lobby.updated",
        entity_type="draft_room",
        entity_id=session_id,
        payload={"action": "ready", "seat_id": seat.id, "user_id": current_user.id, "ready": payload.ready},
    )
    db.commit()
    return get_mock_draft_lobby(session_id, db, current_user)


@router.post("/{session_id}/lobby/heartbeat", response_model=MockDraftSessionRead)
def heartbeat_mock_draft_lobby(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftSessionRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
    _upsert_mock_lobby_member(db, session_id=session_id, seat_id=seat.id, user_id=current_user.id, set_ready=None)
    _emit_mock_draft_event(
        db,
        session_id=session_id,
        event_type="draft.lobby.updated",
        entity_type="draft_room",
        entity_id=session_id,
        payload={"action": "heartbeat", "seat_id": seat.id, "user_id": current_user.id},
    )
    db.commit()
    return get_mock_draft_lobby(session_id, db, current_user)


@router.post("/{session_id}/status", response_model=MockDraftRoomRead)
def update_mock_draft_status(
    session_id: int,
    payload: MockDraftStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRoomRead:
    session_row = _require_mock_commissioner(db, session_id, current_user)
    session_row = (
        db.query(MockDraftSession)
        .filter(MockDraftSession.id == session_id)
        .with_for_update()
        .first()
    )
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock draft not found")
    timer_state = _get_or_create_mock_timer_state(db, session_id)
    now_utc = datetime.now(timezone.utc)
    if payload.status == "lobby_open":
        session_row.status = "lobby_open"
        _pause_draft_timer(timer_state=timer_state, now_utc=now_utc)
    elif payload.status == "countdown":
        _assign_cpu_seats(db, session_row=session_row)
        _apply_random_draft_order(db, session_row=session_row)
        session_row.status = "countdown"
        _reset_draft_timer_for_next_pick(timer_state=timer_state, now_utc=now_utc, transition_seconds=0)
    elif payload.status == "active":
        if session_row.status == "paused":
            session_row.status = "live"
            _start_or_resume_draft_timer(timer_state=timer_state, now_utc=now_utc)
        else:
            session_row.status = "countdown"
            session_row.draft_datetime_utc = now_utc
            _reset_draft_timer_for_next_pick(timer_state=timer_state, now_utc=now_utc, transition_seconds=0)
    elif payload.status == "paused":
        session_row.status = "paused"
        _pause_draft_timer(timer_state=timer_state, now_utc=now_utc)
    elif payload.status == "abandoned":
        session_row.status = "abandoned"
        _pause_draft_timer(timer_state=timer_state, now_utc=now_utc)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported draft status transition")
    db.add(session_row)
    db.add(timer_state)
    _emit_mock_draft_event(
        db,
        session_id=session_id,
        event_type="draft.status.changed",
        entity_type="draft_room",
        entity_id=session_id,
        payload={"status": session_row.status},
    )
    db.commit()
    return _mock_room_state(db, session_row, current_user)


@router.get("/{session_id}/room", response_model=MockDraftRoomRead)
def get_mock_draft_room(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRoomRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    _autopick_timed_out_current_seat(db, session_row=session_row)
    return _mock_room_state(db, session_row, current_user)


@router.get("/{session_id}/snapshot", response_model=MockDraftRoomSnapshotRead)
def get_mock_draft_snapshot(
    session_id: int,
    since_seq: int = 0,
    limit: int = 250,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftRoomSnapshotRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    room = _mock_room_state(db, session_row, current_user)
    events = list_mock_draft_events_since(db, session_id=session_id, since_seq=max(0, since_seq), limit=limit)
    envelopes = [_mock_room_event_envelope(row) for row in events]
    latest_seq = latest_mock_draft_event_seq(db, session_id=session_id)
    return MockDraftRoomSnapshotRead(draft_room=room, events=envelopes, latest_seq=latest_seq)


@router.websocket("/{session_id}/ws")
async def mock_draft_ws_endpoint(websocket: WebSocket, session_id: int) -> None:
    token = websocket.query_params.get("token")
    with SessionLocal() as db:
        try:
            current_user = _get_user_from_ws_token(db, token)
            session_row = _get_mock_draft_or_404(db, session_id)
            initial_room = _mock_room_state(db, session_row, current_user)
        except HTTPException as exc:
            close_code = 4401 if exc.status_code == status.HTTP_401_UNAUTHORIZED else 4403
            await websocket.close(code=close_code)
            return
    room_key = _mock_room_key(session_id)
    await draft_realtime_manager.connect(room_key, websocket)
    try:
        await websocket.send_json(
            {
                "event": "draft_room_ready",
                "event_id": f"snapshot_{session_id}_{initial_room.server_state_seq}",
                "event_type": "draft.room.snapshot",
                "entity_type": "draft_room",
                "entity_id": initial_room.draft_room_id,
                "seq": initial_room.server_state_seq,
                "schema_version": EVENT_SCHEMA_VERSION,
                "room_key": room_key,
                "mock_draft_id": session_id,
                "at": datetime.now(timezone.utc).isoformat(),
                "payload": {"draft_room": initial_room.model_dump(mode="json")},
            }
        )
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"event": "pong", "room_key": room_key, "payload": {}})
    except WebSocketDisconnect:
        await draft_realtime_manager.disconnect(room_key, websocket)
    except Exception:
        await draft_realtime_manager.disconnect(room_key, websocket)


@router.post("/{session_id}/pick", response_model=MockDraftRoomRead)
def make_mock_draft_pick(
    session_id: int,
    payload: MockDraftPickCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> MockDraftRoomRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    resolved_idempotency_key = idempotency_key.strip() if idempotency_key else None
    if resolved_idempotency_key:
        existing_for_key = (
            db.query(MockDraftPick)
            .filter(MockDraftPick.session_id == session_id, MockDraftPick.idempotency_key == resolved_idempotency_key)
            .first()
        )
        if existing_for_key:
            if existing_for_key.player_id != payload.player_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key already used with a different player.")
            return _mock_room_state(db, session_row, current_user)
    try:
        with db.begin_nested():
            session_row = (
                db.query(MockDraftSession)
                .filter(MockDraftSession.id == session_id)
                .with_for_update()
                .first()
            )
            if session_row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock draft not found")
            if session_row.status == "completed":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")
            if session_row.status != "live":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft is not active")
            timer_state = _get_or_create_mock_timer_state(db, session_id)
            seats = _ordered_mock_seats(db, session_id)
            existing_picks = db.query(MockDraftPick).filter(MockDraftPick.session_id == session_id).count()
            total_picks = _total_picks_for_session(session_row)
            round_number, round_pick, current_seat = _draft_pick_seat_for_number(seats, existing_picks + 1)
            if current_seat is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft cannot determine current team")
            if current_user.id != current_seat.owner_user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not on the clock.")
            now_utc = datetime.now(timezone.utc)
            prep_remaining = _draft_pick_prep_remaining_seconds(session_row=session_row, timer_state=timer_state, now_utc=now_utc)
            if prep_remaining > 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Next pick begins in {prep_remaining}s.")
            seconds_remaining = _seconds_remaining_for_current_pick(session_row=session_row, timer_state=timer_state, now_utc=now_utc)
            if seconds_remaining is not None and seconds_remaining <= 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pick clock expired. Auto-pick will submit this turn.")
            player = db.query(Player).filter(Player.id == payload.player_id).with_for_update().first()
            if not player:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
            existing_player_pick = (
                db.query(MockDraftPick)
                .filter(MockDraftPick.session_id == session_id, MockDraftPick.player_id == player.id)
                .first()
            )
            if existing_player_pick:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Player already drafted.")
            existing_roster_entry = (
                db.query(MockDraftRosterEntry)
                .filter(MockDraftRosterEntry.session_id == session_id, MockDraftRosterEntry.player_id == player.id)
                .first()
            )
            if existing_roster_entry:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Player already drafted.")
            current_roster = db.query(MockDraftRosterEntry).filter(MockDraftRosterEntry.seat_id == current_seat.id).all()
            fit = can_draft_position(player.position, current_roster, session_row.roster_slots_json)
            if not fit.can_draft or not fit.destination_slot:
                detail = "invalid player position" if fit.reason == "invalid player position" else DRAFT_POSITION_FULL_REASON
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
            db.add(
                MockDraftPick(
                    session_id=session_id,
                    seat_id=current_seat.id,
                    player_id=player.id,
                    made_by_user_id=current_user.id,
                    round_number=round_number,
                    round_pick=round_pick,
                    overall_pick=existing_picks + 1,
                    idempotency_key=resolved_idempotency_key,
                )
            )
            db.flush()
            db.add(
                MockDraftRosterEntry(
                    session_id=session_id,
                    seat_id=current_seat.id,
                    player_id=player.id,
                    slot=fit.destination_slot,
                    status="active",
                )
            )
            db.flush()
            _remove_player_from_mock_queues(db, session_id=session_id, player_id=player.id)
            _reset_draft_timer_for_next_pick(timer_state=timer_state, now_utc=now_utc, transition_seconds=DRAFT_PICK_TRANSITION_SECONDS)
            if total_picks and (existing_picks + 1) >= total_picks:
                session_row.status = "completed"
                session_row.completed_at = now_utc
                timer_state.paused_at = now_utc
            db.add(session_row)
            db.add(timer_state)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Player already drafted.") from exc
    room = _mock_room_state(db, session_row, current_user)
    _emit_mock_draft_event(
        db,
        session_id=session_id,
        event_type="draft.pick.made",
        entity_type="draft_room",
        entity_id=session_id,
        payload={"player_id": payload.player_id},
    )
    db.commit()
    return room


@router.get("/{session_id}/queue", response_model=MockDraftQueueRead)
def get_mock_draft_queue(
    session_id: int,
    seat_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftQueueRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    if seat_id is None:
        seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
        seat_id = seat.id
    return _draft_queue_state(db, session_row=session_row, seat_id=seat_id)


@router.post("/{session_id}/queue", response_model=MockDraftQueueRead)
def add_mock_draft_queue_item(
    session_id: int,
    payload: MockDraftQueueAddRequest,
    seat_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftQueueRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    if seat_id is None:
        seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
        seat_id = seat.id
    existing_count = db.query(MockDraftQueueItem.id).filter(MockDraftQueueItem.session_id == session_id, MockDraftQueueItem.seat_id == seat_id).count()
    existing = (
        db.query(MockDraftQueueItem)
        .filter(MockDraftQueueItem.session_id == session_id, MockDraftQueueItem.seat_id == seat_id, MockDraftQueueItem.player_id == payload.player_id)
        .first()
    )
    if existing is None:
        db.add(
            MockDraftQueueItem(
                session_id=session_id,
                seat_id=seat_id,
                player_id=payload.player_id,
                priority=existing_count + 1,
            )
        )
        db.flush()
    db.commit()
    return _draft_queue_state(db, session_row=session_row, seat_id=seat_id)


@router.post("/{session_id}/queue/reorder", response_model=MockDraftQueueRead)
def reorder_mock_draft_queue(
    session_id: int,
    payload: MockDraftQueueReorderRequest,
    seat_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftQueueRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    if seat_id is None:
        seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
        seat_id = seat.id
    rows = _normalize_queue_priorities(db, session_id=session_id, seat_id=seat_id)
    by_player_id = {row.player_id: row for row in rows}
    for index, player_id in enumerate(payload.player_ids, start=1):
        row = by_player_id.get(player_id)
        if row is None:
            continue
        row.priority = index
        db.add(row)
    db.flush()
    _normalize_queue_priorities(db, session_id=session_id, seat_id=seat_id)
    db.commit()
    return _draft_queue_state(db, session_row=session_row, seat_id=seat_id)


@router.delete("/{session_id}/queue/{player_id}", response_model=MockDraftQueueRead)
def remove_mock_draft_queue_item(
    session_id: int,
    player_id: int,
    seat_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftQueueRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    if seat_id is None:
        seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
        seat_id = seat.id
    (
        db.query(MockDraftQueueItem)
        .filter(MockDraftQueueItem.session_id == session_id, MockDraftQueueItem.seat_id == seat_id, MockDraftQueueItem.player_id == player_id)
        .delete(synchronize_session=False)
    )
    db.flush()
    _normalize_queue_priorities(db, session_id=session_id, seat_id=seat_id)
    db.commit()
    return _draft_queue_state(db, session_row=session_row, seat_id=seat_id)


@router.post("/{session_id}/queue/clear", response_model=MockDraftQueueRead)
def clear_mock_draft_queue(
    session_id: int,
    seat_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MockDraftQueueRead:
    session_row = _get_mock_draft_or_404(db, session_id)
    if seat_id is None:
        seat = _resolve_user_mock_seat(db, session_row=session_row, current_user=current_user)
        seat_id = seat.id
    (
        db.query(MockDraftQueueItem)
        .filter(MockDraftQueueItem.session_id == session_id, MockDraftQueueItem.seat_id == seat_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return _draft_queue_state(db, session_row=session_row, seat_id=seat_id)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mock_draft(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    session_row = _require_mock_commissioner(db, session_id, current_user)
    db.delete(session_row)
    db.commit()
