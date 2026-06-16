import math
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from api.app.api.deps import require_league_member
from api.app.models.draft import Draft
from api.app.models.draft_lobby_member import DraftLobbyMember
from api.app.models.draft_pick import DraftPick
from api.app.models.draft_team_queue_item import DraftTeamQueueItem
from api.app.models.draft_timer_state import DraftTimerState
from api.app.models.league import League
from api.app.models.league_settings import LeagueSettings
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.models.user import User
from api.app.models.weekly_projection import WeeklyProjection
from api.app.schemas.draft_room import (
    DraftPickCreate,
    DraftRoomPickRead,
    DraftRoomRead,
    DraftRoomStatusUpdateRequest,
    DraftRoomTeamRead,
)
from api.app.services.admin_actions import append_admin_action
from api.app.services.draft_engine import get_total_picks, is_draft_complete
from api.app.services.event_stream import append_league_event, latest_league_event_seq
from api.app.services.league_flow import FIXED_ROSTER_SLOTS


OFFENSE_DRAFT_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
DRAFT_POSITION_FULL_REASON = "You cannot draft this position because your roster has no available slot for it."
DRAFT_POSITION_LOCK_REASON = "Roster full for this position"
DRAFTABLE_SLOT_KEYS = {"QB", "RB", "WR", "TE", "K", "DEF", "FLEX", "SUPERFLEX", "BENCH"}
FLEX_ELIGIBLE_POSITIONS = {"RB", "WR", "TE"}
SUPERFLEX_ELIGIBLE_POSITIONS = {"QB", "RB", "WR", "TE"}
DRAFT_LOBBY_COUNTDOWN_SECONDS = 60
DRAFT_LOBBY_CONNECTED_TTL_SECONDS = 25
DRAFT_AUTOPICKS_ENABLED = True
DRAFT_CPU_AUTOPICK_BUFFER_SECONDS = 2
EVENT_SCHEMA_VERSION = 1
DRAFT_STATUS_MAP = {
    "filling": "waiting",
    "lobby_open": "waiting",
    "countdown": "waiting",
    "scheduled": "waiting",
    "live": "active",
    "paused": "paused",
    "completed": "complete",
    "abandoned": "complete",
}


@dataclass(frozen=True)
class DraftPositionFit:
    can_draft: bool
    reason: str | None = None
    destination_slot: str | None = None


def get_draft_room_state(db: Session, league: League, current_user: User) -> DraftRoomRead:
    require_league_member(db, league.id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")

    teams = get_ordered_draft_teams(db, league.id)
    picks_rows = (
        db.query(DraftPick, Team, Player)
        .join(Team, Team.id == DraftPick.team_id)
        .join(Player, Player.id == DraftPick.player_id)
        .filter(DraftPick.draft_id == draft_row.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )
    drafted_player_ids = [player.id for _pick, _team, player in picks_rows]

    roster_rows = (
        db.query(RosterEntry, Team, Player)
        .join(Team, Team.id == RosterEntry.team_id)
        .join(Player, Player.id == RosterEntry.player_id)
        .filter(RosterEntry.league_id == league.id)
        .order_by(Team.id.asc(), RosterEntry.created_at.asc())
        .all()
    )

    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    slot_order = [slot for slot in roster_slots.keys()]
    if "BENCH" not in slot_order:
        slot_order.append("BENCH")
    if "IR" not in slot_order:
        slot_order.append("IR")
    if "FLEX" not in slot_order and "SUPERFLEX" not in slot_order:
        slot_order.append("FLEX")

    roster_rows_by_team: dict[int, list[tuple[RosterEntry, Team, Player]]] = {}
    for row in roster_rows:
        roster_rows_by_team.setdefault(row[1].id, []).append(row)

    rosters_by_team = []
    for team in teams:
        team_rows = roster_rows_by_team.get(team.id, [])
        position_counts: dict[str, int] = {}
        slots: dict[str, list] = {slot: [] for slot in slot_order}
        total_projected_points = 0.0

        for roster_entry, _team, player in team_rows:
            position_counts[player.position] = position_counts.get(player.position, 0) + 1
            slot_name = "FLEX" if roster_entry.slot == "SUPERFLEX" else roster_entry.slot
            if slot_name not in slots:
                slots[slot_name] = []
            projected = (
                float(player.sheet_projected_season_points)
                if player.sheet_projected_season_points is not None
                else None
            )
            if projected is not None:
                total_projected_points += projected
            slots[slot_name].append(
                {
                    "player_id": player.id,
                    "player_name": player.name,
                    "position": player.position,
                    "school": player.school,
                    "slot": slot_name,
                    "projected_fantasy_points": projected,
                }
            )

        rosters_by_team.append(
            {
                "team_id": team.id,
                "team_name": team.name,
                "total_projected_points": round(total_projected_points, 1),
                "position_counts": position_counts,
                "slots": slots,
            }
        )

    total_rounds = _total_roster_slot_rounds(settings_row=settings_row)
    total_picks = _total_draft_picks_for_league(settings_row=settings_row, team_count=len(teams))
    draft_complete = is_draft_complete(len(picks_rows), total_picks) or draft_row.status == "completed"
    current_pick = min(len(picks_rows) + 1, total_picks) if total_picks else len(picks_rows) + 1
    current_round, current_round_pick, current_team = get_draft_pick_team_for_number(teams, current_pick)
    if draft_complete:
        current_team = None

    current_team_roster_entries = (
        [
            roster_entry
            for roster_entry, _team, _player in roster_rows_by_team.get(current_team.id, [])
        ]
        if current_team
        else []
    )
    position_eligibility: dict[str, dict[str, str | bool | None]] = {}
    for position in ("QB", "RB", "WR", "TE", "K"):
        fit = (
            can_draft_position(position, current_team_roster_entries, settings_row)
            if current_team
            else DraftPositionFit(can_draft=False, reason="Draft is complete.", destination_slot=None)
        )
        reason = DRAFT_POSITION_LOCK_REASON if fit.reason == DRAFT_POSITION_FULL_REASON else fit.reason
        position_eligibility[position] = {
            "can_draft": fit.can_draft,
            "reason": reason,
            "destination_slot": fit.destination_slot,
        }

    timer_state = db.query(DraftTimerState).filter(DraftTimerState.draft_id == draft_row.id).first()
    timer_started_at = timer_state.timer_started_at if timer_state else None
    timer_paused_at = timer_state.paused_at if timer_state else None
    timer_paused_total_seconds = int(timer_state.paused_total_seconds if timer_state else 0)
    now_utc = datetime.now(timezone.utc)
    prep_remaining = _draft_pick_prep_remaining_seconds(
        draft_row=draft_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )

    user_team = next((team for team in teams if team.owner_user_id == current_user.id), None)
    lobby_presence_by_team, lobby_joined_count, lobby_connected_count, lobby_ready_count = _lobby_presence_summary(
        db,
        draft_id=draft_row.id,
        teams=teams,
        now_utc=now_utc,
    )

    seconds_remaining: int | None = None
    current_pick_expires_at = _as_utc(draft_row.current_pick_expires_at)
    if draft_row.status in {"scheduled", "countdown", "live", "paused"}:
        seconds_remaining = _seconds_remaining_for_current_pick(
            draft_row=draft_row,
            timer_state=timer_state,
            now_utc=now_utc,
        )
        if (
            current_pick_expires_at is None
            and seconds_remaining is not None
            and draft_row.status != "paused"
            and current_team is not None
        ):
            current_pick_expires_at = now_utc + timedelta(seconds=seconds_remaining)

    has_time_remaining = seconds_remaining is None or seconds_remaining > 0
    can_make_pick = bool(
        draft_row.status == "live"
        and current_team
        and prep_remaining <= 0
        and has_time_remaining
        and (
            current_user.id == league.commissioner_user_id
            or current_user.id == current_team.owner_user_id
        )
    )

    phase_type: str | None = None
    phase_seconds_remaining: int | None = None
    current_pick_timer_seconds = int(draft_row.pick_timer_seconds)
    if draft_row.status == "scheduled":
        phase_type = "lobby_countdown"
        phase_seconds_remaining = seconds_remaining
    elif draft_row.status == "countdown":
        phase_type = "prestart_countdown"
        phase_seconds_remaining = seconds_remaining
    elif draft_row.status in {"live", "paused"}:
        if prep_remaining > 0:
            phase_type = "pick_transition"
            phase_seconds_remaining = prep_remaining
        else:
            phase_type = "pick_clock"
            phase_seconds_remaining = seconds_remaining

    pick_state = "PICK_SUBMITTED" if phase_type == "pick_transition" else "WAITING_FOR_PICK"
    drafted_player_ids_subquery = db.query(DraftPick.player_id).filter(DraftPick.draft_id == draft_row.id)
    rostered_player_ids_subquery = db.query(RosterEntry.player_id).filter(RosterEntry.league_id == league.id)
    available_player_count = (
        db.query(func.count(Player.id))
        .filter(Player.position.in_(tuple(OFFENSE_DRAFT_POSITIONS)))
        .filter(~Player.id.in_(drafted_player_ids_subquery))
        .filter(~Player.id.in_(rostered_player_ids_subquery))
        .scalar()
        or 0
    )
    server_state_seq = latest_league_event_seq(db, league_id=league.id)

    return DraftRoomRead(
        draft_room_id=draft_row.id,
        league_id=league.id,
        draft_id=draft_row.id,
        status=draft_row.status,
        draft_status=_draft_status_value(draft_row.status),
        server_time=now_utc,
        pick_timer_seconds=draft_row.pick_timer_seconds,
        total_rounds=total_rounds,
        total_picks=total_picks,
        is_complete=draft_complete,
        can_exit=draft_complete,
        email_history_available=draft_complete,
        roster_slots=roster_slots,
        position_eligibility=position_eligibility,
        draft_order=[team.id for team in teams],
        drafted_player_ids=drafted_player_ids,
        available_player_count=int(available_player_count),
        rosters_by_team=rosters_by_team,
        lobby_ready_count=lobby_ready_count,
        lobby_joined_count=lobby_joined_count,
        lobby_connected_count=lobby_connected_count,
        teams=[
            DraftRoomTeamRead(
                id=team.id,
                name=team.name,
                owner_user_id=team.owner_user_id,
                owner_name=team.owner_name,
                lobby_joined=bool(lobby_presence_by_team.get(team.id, {}).get("joined")),
                lobby_connected=bool(lobby_presence_by_team.get(team.id, {}).get("connected")),
                lobby_ready=bool(lobby_presence_by_team.get(team.id, {}).get("ready")),
            )
            for team in teams
        ],
        picks=[
            DraftRoomPickRead(
                id=pick.id,
                overall_pick=pick.overall_pick,
                round_number=pick.round_number,
                round_pick=pick.round_pick,
                team_id=team.id,
                team_name=team.name,
                player_id=player.id,
                player_name=player.name,
                player_position=player.position,
                player_school=player.school,
                made_by_user_id=pick.made_by_user_id,
                created_at=pick.created_at,
            )
            for pick, team, player in picks_rows
        ],
        current_pick=current_pick,
        current_round=current_round,
        current_round_pick=current_round_pick,
        current_team_id=current_team.id if current_team else None,
        current_team_name=current_team.name if current_team else None,
        current_pick_started_at=_as_utc(draft_row.current_pick_started_at),
        current_pick_expires_at=current_pick_expires_at,
        seconds_remaining=seconds_remaining,
        phase_seconds_remaining=phase_seconds_remaining,
        phase_type=phase_type,
        pick_state=pick_state,
        auto_pick_seconds_remaining=None,
        current_pick_timer_seconds=current_pick_timer_seconds,
        timer_started_at=timer_started_at,
        timer_paused_at=timer_paused_at,
        timer_paused_total_seconds=timer_paused_total_seconds,
        server_state_seq=server_state_seq,
        user_team_id=user_team.id if user_team else None,
        can_make_pick=can_make_pick,
        created_at=draft_row.created_at,
        updated_at=draft_row.updated_at,
    )


def get_ordered_draft_teams(db: Session, league_id: int) -> list[Team]:
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    if not teams:
        return []

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    scoring_json = settings_row.scoring_json if settings_row and isinstance(settings_row.scoring_json, dict) else {}
    meta = scoring_json.get("__meta__", {}) if isinstance(scoring_json.get("__meta__", {}), dict) else {}
    order_ids = meta.get("draft_order_team_ids")

    if isinstance(order_ids, list) and order_ids:
        index_by_team_id = {
            int(team_id): index
            for index, team_id in enumerate(order_ids)
            if isinstance(team_id, int)
        }
        if index_by_team_id:
            return sorted(
                teams,
                key=lambda team: (
                    index_by_team_id.get(team.id, len(index_by_team_id) + team.id),
                    team.id,
                ),
            )

    # MVP real draft order is deterministic join order until an explicit draft-order table exists.
    return sorted(teams, key=lambda team: (team.created_at, team.id))


def get_draft_pick_team_for_number(
    teams: list[Team],
    pick_number: int,
) -> tuple[int, int, Team | None]:
    if not teams or pick_number <= 0:
        return 0, 0, None
    team_count = len(teams)
    round_number = ((pick_number - 1) // team_count) + 1
    zero_based_round_pick = (pick_number - 1) % team_count
    round_pick = zero_based_round_pick + 1
    index = zero_based_round_pick if round_number % 2 == 1 else team_count - 1 - zero_based_round_pick
    return round_number, round_pick, teams[index]


def assign_draft_roster_slot(
    db: Session,
    settings_row: LeagueSettings,
    team_id: int,
    player_position: str,
) -> str:
    roster_entries = db.query(RosterEntry).filter(RosterEntry.team_id == team_id).all()
    fit = can_draft_position(player_position, roster_entries, settings_row)
    if not fit.can_draft or not fit.destination_slot:
        detail = "invalid player position" if fit.reason == "invalid player position" else DRAFT_POSITION_FULL_REASON
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    return fit.destination_slot


def _normalize_position(value: str) -> str:
    normalized = (value or "").strip().upper()
    if not normalized:
        return ""
    if normalized in {"DST", "D/ST"} or normalized.startswith("DEF"):
        return "DEF"
    for base in ("QB", "RB", "WR", "TE", "K"):
        if normalized.startswith(base):
            return base
    return normalized


def _canonical_roster_slot_key(value: str) -> str:
    normalized = (value or "").strip().upper()
    if not normalized:
        return ""
    if normalized.startswith("SUPERFLEX"):
        return "SUPERFLEX"
    if normalized.startswith("FLEX"):
        return "FLEX"
    if normalized in {"BE", "BN"} or normalized.startswith("BENCH"):
        return "BENCH"
    if normalized.startswith("IR"):
        return "IR"
    if normalized in {"DST", "D/ST"} or normalized.startswith("DEF"):
        return "DEF"
    for base in ("QB", "RB", "WR", "TE", "K"):
        if normalized.startswith(base):
            return base
    return normalized


def _build_canonical_slot_limits(raw_limits: dict | None) -> dict[str, int]:
    canonical = {
        "QB": 0,
        "RB": 0,
        "WR": 0,
        "TE": 0,
        "FLEX": 0,
        "SUPERFLEX": 0,
        "K": 0,
        "DEF": 0,
        "BENCH": 0,
        "IR": 0,
    }
    for raw_key, raw_value in (raw_limits or {}).items():
        slot_key = _canonical_roster_slot_key(str(raw_key))
        if slot_key not in canonical:
            continue
        try:
            limit = int(raw_value)
        except (TypeError, ValueError):
            continue
        if limit > 0:
            canonical[slot_key] += limit
    return canonical


def _roster_slot_counts(roster: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    if isinstance(roster, dict):
        for raw_slot, raw_value in roster.items():
            slot_key = _canonical_roster_slot_key(str(raw_slot))
            if not slot_key:
                continue
            if isinstance(raw_value, (list, tuple, set)):
                count = len(raw_value)
            else:
                try:
                    count = int(raw_value)
                except (TypeError, ValueError):
                    count = 0
            counts[slot_key] = counts.get(slot_key, 0) + max(0, count)
        return counts

    for entry in roster or []:
        raw_slot = getattr(entry, "slot", None)
        if raw_slot is None and isinstance(entry, dict):
            raw_slot = entry.get("slot")
        slot_key = _canonical_roster_slot_key(str(raw_slot or ""))
        if slot_key:
            counts[slot_key] = counts.get(slot_key, 0) + 1
    return counts


def can_draft_position(
    player_position: str,
    roster: object,
    roster_settings: LeagueSettings | dict,
) -> DraftPositionFit:
    normalized_position = _normalize_position(player_position)
    if not normalized_position:
        return DraftPositionFit(can_draft=False, reason="invalid player position", destination_slot=None)

    if isinstance(roster_settings, LeagueSettings):
        roster_slots = roster_settings.roster_slots_json or FIXED_ROSTER_SLOTS
        superflex_enabled = bool(roster_settings.superflex_enabled)
    else:
        roster_slots = roster_settings or FIXED_ROSTER_SLOTS
        superflex_enabled = bool(roster_slots.get("superflex_enabled", False)) if isinstance(roster_slots, dict) else False

    slot_limits = _build_canonical_slot_limits(roster_slots)
    current_counts = _roster_slot_counts(roster)

    primary_limit = int(slot_limits.get(normalized_position, 0))
    if primary_limit and current_counts.get(normalized_position, 0) < primary_limit:
        return DraftPositionFit(can_draft=True, destination_slot=normalized_position)

    flex_limit = int(slot_limits.get("FLEX", 0))
    if normalized_position in FLEX_ELIGIBLE_POSITIONS and flex_limit and current_counts.get("FLEX", 0) < flex_limit:
        return DraftPositionFit(can_draft=True, destination_slot="FLEX")

    superflex_limit = int(slot_limits.get("SUPERFLEX", 0))
    if (
        superflex_enabled
        and normalized_position in SUPERFLEX_ELIGIBLE_POSITIONS
        and superflex_limit
        and current_counts.get("SUPERFLEX", 0) < superflex_limit
    ):
        return DraftPositionFit(can_draft=True, destination_slot="SUPERFLEX")

    bench_limit = int(slot_limits.get("BENCH", 0))
    if current_counts.get("BENCH", 0) < bench_limit:
        return DraftPositionFit(can_draft=True, destination_slot="BENCH")

    return DraftPositionFit(can_draft=False, reason=DRAFT_POSITION_FULL_REASON, destination_slot=None)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _draft_status_value(status_value: str | None) -> str:
    return DRAFT_STATUS_MAP.get((status_value or "").strip().lower(), "waiting")


def _draftable_roster_rounds_from_slots(roster_slots: dict | None) -> int:
    slot_limits = _build_canonical_slot_limits(roster_slots)
    return sum(int(slot_limits.get(slot, 0)) for slot in DRAFTABLE_SLOT_KEYS)


def _total_draft_picks_for_league(*, settings_row: LeagueSettings, team_count: int) -> int:
    return get_total_picks(team_count, settings_row.roster_slots_json or FIXED_ROSTER_SLOTS)


def _total_roster_slot_rounds(*, settings_row: LeagueSettings) -> int:
    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    return max(1, _draftable_roster_rounds_from_slots(roster_slots))


def _get_or_create_draft_timer_state(db: Session, draft_id: int) -> DraftTimerState:
    timer_state = db.query(DraftTimerState).filter(DraftTimerState.draft_id == draft_id).first()
    if timer_state:
        return timer_state
    timer_state = DraftTimerState(
        draft_id=draft_id,
        timer_started_at=None,
        paused_at=None,
        paused_total_seconds=0,
        last_tick_at=None,
        auto_picking_started_at=None,
        auto_picking_pick_number=None,
        state_version=1,
    )
    db.add(timer_state)
    db.flush()
    return timer_state


def _start_or_resume_draft_timer(
    *,
    timer_state: DraftTimerState,
    now_utc: datetime,
) -> None:
    if timer_state.timer_started_at is None:
        timer_state.timer_started_at = now_utc
    if timer_state.paused_at:
        pause_delta = max(0, int((now_utc - timer_state.paused_at).total_seconds()))
        timer_state.paused_total_seconds += pause_delta
        timer_state.paused_at = None
    timer_state.last_tick_at = now_utc
    timer_state.state_version += 1


def _pause_draft_timer(
    *,
    timer_state: DraftTimerState,
    now_utc: datetime,
) -> None:
    if timer_state.timer_started_at is None:
        timer_state.timer_started_at = now_utc
    if timer_state.paused_at is None:
        timer_state.paused_at = now_utc
    timer_state.last_tick_at = now_utc
    timer_state.state_version += 1


def _reset_draft_timer_for_next_pick(
    *,
    timer_state: DraftTimerState,
    now_utc: datetime,
    transition_seconds: int = 0,
    draft_row: Draft | None = None,
) -> None:
    delay = max(0, int(transition_seconds))
    started_at = now_utc + timedelta(seconds=delay)
    timer_state.timer_started_at = started_at
    timer_state.paused_at = None
    timer_state.paused_total_seconds = 0
    timer_state.last_tick_at = now_utc
    timer_state.auto_picking_started_at = None
    timer_state.auto_picking_pick_number = None
    timer_state.state_version += 1
    if draft_row is not None and draft_row.status != "completed":
        draft_row.current_pick_started_at = started_at
        draft_row.current_pick_expires_at = started_at + timedelta(seconds=max(0, int(draft_row.pick_timer_seconds)))


def _draft_pick_prep_remaining_seconds(
    *,
    draft_row: Draft,
    timer_state: DraftTimerState | None,
    now_utc: datetime,
) -> int:
    if draft_row.status not in {"scheduled", "countdown", "live"}:
        return 0
    timer_started_at = _as_utc(timer_state.timer_started_at) if timer_state else None
    if timer_started_at is None:
        return 0
    return max(0, int(math.ceil((timer_started_at - now_utc).total_seconds())))


def _seconds_remaining_for_current_pick(
    *,
    draft_row: Draft,
    timer_state: DraftTimerState | None,
    now_utc: datetime,
) -> int | None:
    if draft_row.status not in {"scheduled", "countdown", "live", "paused"}:
        return None
    if draft_row.status == "scheduled":
        start_at = _as_utc(draft_row.draft_datetime_utc)
        if start_at is None:
            return None
        return max(0, int(math.ceil((start_at - now_utc).total_seconds())))
    if draft_row.status == "countdown":
        timer_started_at = _as_utc(timer_state.timer_started_at) if timer_state else None
        anchor_started_at = timer_started_at or _as_utc(draft_row.updated_at) or _as_utc(draft_row.created_at)
        if not anchor_started_at:
            return DRAFT_LOBBY_COUNTDOWN_SECONDS
        elapsed_seconds = max(0, int((now_utc - anchor_started_at).total_seconds()))
        return max(0, int(DRAFT_LOBBY_COUNTDOWN_SECONDS) - elapsed_seconds)

    prep_remaining = _draft_pick_prep_remaining_seconds(
        draft_row=draft_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )
    pick_window_seconds = int(draft_row.pick_timer_seconds)
    if prep_remaining > 0:
        return pick_window_seconds + prep_remaining
    current_pick_expires_at = _as_utc(draft_row.current_pick_expires_at)
    if current_pick_expires_at is not None:
        if draft_row.status == "paused" and timer_state and timer_state.paused_at is not None:
            paused_at = _as_utc(timer_state.paused_at) or now_utc
            return max(0, int(math.ceil((current_pick_expires_at - paused_at).total_seconds())))
        return max(0, int(math.ceil((current_pick_expires_at - now_utc).total_seconds())))

    timer_started_at = timer_state.timer_started_at if timer_state else None
    timer_paused_at = timer_state.paused_at if timer_state else None
    timer_paused_total_seconds = int(timer_state.paused_total_seconds if timer_state else 0)
    anchor_started_at = _as_utc(timer_started_at) or _as_utc(draft_row.updated_at) or _as_utc(draft_row.created_at)
    if not anchor_started_at:
        return None
    elapsed_until = now_utc
    if draft_row.status == "paused" and timer_paused_at is not None:
        elapsed_until = _as_utc(timer_paused_at) or now_utc
    elapsed_seconds = max(
        0,
        int((elapsed_until - anchor_started_at).total_seconds()) - timer_paused_total_seconds,
    )
    return max(0, pick_window_seconds - elapsed_seconds)


def _complete_draft(
    *,
    draft_row: Draft,
    league: League,
    timer_state: DraftTimerState | None,
    now_utc: datetime,
) -> None:
    draft_row.status = "completed"
    draft_row.completed_at = draft_row.completed_at or now_utc
    draft_row.current_pick_expires_at = None
    league.status = "post_draft"
    if timer_state is not None:
        timer_state.paused_at = now_utc
        timer_state.last_tick_at = now_utc
        timer_state.state_version += 1


def _start_scheduled_draft_on_first_pick(
    *,
    draft_row: Draft,
    league: League,
    timer_state: DraftTimerState,
    now_utc: datetime,
) -> None:
    # Phase 1 MVP behavior: the first successful pick intentionally opens a scheduled real draft.
    draft_row.status = "live"
    league.status = "draft_live"
    _reset_draft_timer_for_next_pick(
        timer_state=timer_state,
        now_utc=now_utc,
        transition_seconds=0,
        draft_row=draft_row,
    )


def _lobby_presence_summary(
    db: Session,
    *,
    draft_id: int,
    teams: list[Team],
    now_utc: datetime,
) -> tuple[dict[int, dict[str, bool]], int, int, int]:
    rows = db.query(DraftLobbyMember).filter(DraftLobbyMember.draft_id == draft_id).all()
    connected_cutoff = now_utc - timedelta(seconds=DRAFT_LOBBY_CONNECTED_TTL_SECONDS)
    by_team: dict[int, dict[str, bool]] = {
        team.id: {
            "joined": team.owner_user_id is None,
            "connected": team.owner_user_id is None,
            "ready": team.owner_user_id is None,
        }
        for team in teams
    }
    joined_count = sum(1 for team in teams if team.owner_user_id is None)
    connected_count = joined_count
    ready_count = joined_count

    for row in rows:
        flags = by_team.get(row.team_id)
        if flags is None:
            continue
        last_seen = _as_utc(row.last_seen_at)
        connected = bool(last_seen and last_seen >= connected_cutoff)
        joined = True
        ready = bool(row.is_ready)

        if not flags["joined"] and joined:
            joined_count += 1
        if not flags["connected"] and connected:
            connected_count += 1
        if not flags["ready"] and ready:
            ready_count += 1

        flags["joined"] = flags["joined"] or joined
        flags["connected"] = flags["connected"] or connected
        flags["ready"] = flags["ready"] or ready

    return by_team, joined_count, connected_count, ready_count


def _remove_player_from_draft_queues(
    db: Session,
    *,
    draft_id: int,
    player_id: int,
) -> None:
    try:
        with db.begin_nested():
            (
                db.query(DraftTeamQueueItem)
                .filter(
                    DraftTeamQueueItem.draft_id == draft_id,
                    DraftTeamQueueItem.player_id == player_id,
                )
                .delete(synchronize_session=False)
            )
            db.flush()
    except ProgrammingError:
        db.expire_all()


def _team_roster_entries(db: Session, team_id: int) -> list[RosterEntry]:
    return db.query(RosterEntry).filter(RosterEntry.team_id == team_id).all()


def _ordered_autopick_candidates(
    db: Session,
    *,
    draft_id: int,
    league_id: int,
    limit: int = 300,
) -> list[Player]:
    drafted_player_ids_subquery = db.query(DraftPick.player_id).filter(DraftPick.draft_id == draft_id)
    rostered_player_ids_subquery = db.query(RosterEntry.player_id).filter(RosterEntry.league_id == league_id)
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
        .filter(~Player.id.in_(drafted_player_ids_subquery))
        .filter(~Player.id.in_(rostered_player_ids_subquery))
    )

    sheet_projection_points = func.coalesce(Player.sheet_projected_season_points, -1.0)
    if latest_projection_window:
        projection_points = func.coalesce(WeeklyProjection.fantasy_points, 0.0)
        query = query.outerjoin(
            WeeklyProjection,
            and_(
                WeeklyProjection.player_id == Player.id,
                WeeklyProjection.season == int(latest_projection_window[0]),
                WeeklyProjection.week == int(latest_projection_window[1]),
            ),
        ).order_by(
            adp_missing.asc(),
            adp_non_positive.asc(),
            Player.sheet_adp.asc(),
            sheet_projection_points.desc(),
            projection_points.desc(),
            Player.id.asc(),
        )
    else:
        query = query.order_by(
            adp_missing.asc(),
            adp_non_positive.asc(),
            Player.sheet_adp.asc(),
            sheet_projection_points.desc(),
            Player.id.asc(),
        )

    return query.limit(limit).all()


def _advance_countdown_if_ready(
    db: Session,
    *,
    league: League,
    draft_row: Draft,
    timer_state: DraftTimerState,
    now_utc: datetime,
) -> bool:
    if draft_row.status != "countdown":
        return False

    seconds_remaining = _seconds_remaining_for_current_pick(
        draft_row=draft_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )
    if seconds_remaining is None or seconds_remaining > 0:
        return False

    draft_row.status = "live"
    if league.status != "post_draft":
        league.status = "draft_live"
    _reset_draft_timer_for_next_pick(
        timer_state=timer_state,
        now_utc=now_utc,
        transition_seconds=0,
        draft_row=draft_row,
    )
    db.add(draft_row)
    db.add(timer_state)
    db.add(league)
    return True


def _emit_draft_event(
    db: Session,
    *,
    league_id: int,
    event_type: str,
    payload: dict | None = None,
    entity_type: str = "league",
    entity_id: int | None = None,
) -> None:
    append_league_event(
        db,
        league_id=league_id,
        event_type=event_type,
        payload=payload or {},
        entity_type=entity_type,
        entity_id=entity_id,
        schema_version=EVENT_SCHEMA_VERSION,
    )


def _draft_conflict_detail(exc: IntegrityError) -> str:
    raw = str(getattr(exc, "orig", exc)).lower()
    if "idempotency" in raw:
        return "draft state changed; refresh and try again"
    if "roster" in raw or "league_player" in raw or "team_player" in raw:
        return "player already on a league roster"
    if "player" in raw or "draft_player" in raw:
        return "player already drafted"
    return "draft state changed; refresh and try again"


def autopick_timed_out_current_team(
    db: Session,
    *,
    league: League,
    current_user: User | None,
    force: bool = False,
) -> bool:
    if not DRAFT_AUTOPICKS_ENABLED:
        return False

    now_utc = datetime.now(timezone.utc)
    changed = False
    transitioned_to_countdown = False
    transitioned_to_live = False
    autopick_committed = False

    try:
        with db.begin_nested():
            draft_row = (
                db.query(Draft)
                .filter(Draft.league_id == league.id)
                .with_for_update()
                .first()
            )
            if not draft_row:
                return False

            settings_row = (
                db.query(LeagueSettings)
                .filter(LeagueSettings.league_id == league.id)
                .with_for_update()
                .first()
            )
            if not settings_row:
                return False

            timer_state = (
                db.query(DraftTimerState)
                .filter(DraftTimerState.draft_id == draft_row.id)
                .with_for_update()
                .first()
            )
            if not timer_state:
                timer_state = _get_or_create_draft_timer_state(db, draft_row.id)
                db.flush()

            teams = get_ordered_draft_teams(db, league.id)
            if not teams:
                return False

            if _advance_countdown_if_ready(
                db,
                league=league,
                draft_row=draft_row,
                timer_state=timer_state,
                now_utc=now_utc,
            ):
                changed = True
                if draft_row.status == "countdown":
                    transitioned_to_countdown = True
                elif draft_row.status == "live":
                    transitioned_to_live = True
                return changed

            if draft_row.status != "live":
                return False

            total_picks = _total_draft_picks_for_league(settings_row=settings_row, team_count=len(teams))
            existing_picks = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
            if is_draft_complete(existing_picks, total_picks):
                _complete_draft(draft_row=draft_row, league=league, timer_state=timer_state, now_utc=now_utc)
                db.add(draft_row)
                db.add(league)
                db.add(timer_state)
                changed = True
                return changed

            round_number, round_pick, current_team = get_draft_pick_team_for_number(teams, existing_picks + 1)
            if current_team is None:
                return False

            current_pick_number = existing_picks + 1
            seconds_remaining = _seconds_remaining_for_current_pick(
                draft_row=draft_row,
                timer_state=timer_state,
                now_utc=now_utc,
            )
            if seconds_remaining is None:
                return False

            autopick_trigger_seconds = 0
            if current_team.owner_user_id is None:
                autopick_trigger_seconds = max(
                    0,
                    int(draft_row.pick_timer_seconds) - int(DRAFT_CPU_AUTOPICK_BUFFER_SECONDS),
                )

            if not force and seconds_remaining > autopick_trigger_seconds:
                return False

            pick_idempotency = f"timeout:{draft_row.id}:{current_pick_number}"
            existing_timeout_pick = (
                db.query(DraftPick)
                .filter(
                    DraftPick.draft_id == draft_row.id,
                    DraftPick.idempotency_key == pick_idempotency,
                )
                .first()
            )
            if existing_timeout_pick:
                return False

            selected_player: Player | None = None
            selected_slot: str | None = None
            current_team_roster = _team_roster_entries(db, current_team.id)
            candidates = _ordered_autopick_candidates(
                db,
                draft_id=draft_row.id,
                league_id=league.id,
            )
            for candidate in candidates:
                fit = can_draft_position(candidate.position, current_team_roster, settings_row)
                if not fit.can_draft or not fit.destination_slot:
                    continue
                selected_player = candidate
                selected_slot = fit.destination_slot
                break
            if selected_player is None or selected_slot is None:
                return False

            pick = DraftPick(
                draft_id=draft_row.id,
                team_id=current_team.id,
                player_id=selected_player.id,
                made_by_user_id=None,
                round_number=round_number,
                round_pick=round_pick,
                overall_pick=current_pick_number,
                idempotency_key=pick_idempotency,
            )
            db.add(pick)
            db.flush()
            db.add(
                RosterEntry(
                    league_id=league.id,
                    team_id=current_team.id,
                    player_id=selected_player.id,
                    slot=selected_slot,
                    status="active",
                )
            )
            db.flush()
            _remove_player_from_draft_queues(
                db,
                draft_id=draft_row.id,
                player_id=selected_player.id,
            )

            _reset_draft_timer_for_next_pick(
                timer_state=timer_state,
                now_utc=now_utc,
                transition_seconds=0,
                draft_row=draft_row,
            )

            if draft_row.status == "scheduled":
                draft_row.status = "live"
            league.status = "draft_live"
            if is_draft_complete(current_pick_number, total_picks):
                _complete_draft(draft_row=draft_row, league=league, timer_state=timer_state, now_utc=now_utc)

            db.add(draft_row)
            db.add(league)
            db.add(timer_state)
            autopick_committed = True
            changed = True
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_draft_conflict_detail(exc)) from exc

    if changed:
        if transitioned_to_countdown:
            _emit_draft_event(
                db,
                league_id=league.id,
                event_type="draft.status.changed",
                entity_type="draft_room",
                payload={"status": "countdown", "reason": "scheduled_start_reached"},
            )
            _emit_draft_event(
                db,
                league_id=league.id,
                event_type="draft.room.updated",
                entity_type="draft_room",
                payload={"reason": "countdown_started"},
            )
        if transitioned_to_live:
            _emit_draft_event(
                db,
                league_id=league.id,
                event_type="draft.status.changed",
                entity_type="draft_room",
                payload={"status": "live", "reason": "countdown_complete"},
            )
            _emit_draft_event(
                db,
                league_id=league.id,
                event_type="draft.room.updated",
                entity_type="draft_room",
                payload={"reason": "draft_start_visual"},
            )
        if autopick_committed:
            _emit_draft_event(
                db,
                league_id=league.id,
                event_type="draft.pick.made",
                entity_type="draft_pick",
                payload={
                    "reason": "timeout_autopick",
                    "made_by_user_id": current_user.id if current_user else None,
                },
            )
            _emit_draft_event(
                db,
                league_id=league.id,
                event_type="draft.room.updated",
                entity_type="draft_room",
                payload={"reason": "timeout_autopick"},
            )
    return changed


def create_real_draft_pick(
    db: Session,
    league: League,
    payload: DraftPickCreate,
    current_user: User,
    *,
    idempotency_key: str | None = None,
) -> DraftRoomRead:
    require_league_member(db, league.id, current_user)
    resolved_idempotency_key = (idempotency_key or "").strip() or None

    if resolved_idempotency_key:
        existing_for_key = (
            db.query(DraftPick)
            .join(Draft, Draft.id == DraftPick.draft_id)
            .filter(
                Draft.league_id == league.id,
                DraftPick.idempotency_key == resolved_idempotency_key,
            )
            .first()
        )
        if existing_for_key:
            if existing_for_key.player_id != payload.player_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key already used with a different player.",
                )
            return get_draft_room_state(db, league, current_user)

    try:
        with db.begin_nested():
            draft_row = (
                db.query(Draft)
                .filter(Draft.league_id == league.id)
                .with_for_update()
                .first()
            )
            if not draft_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

            if draft_row.status == "completed":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")
            if draft_row.status not in {"scheduled", "live"}:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft is not active")

            settings_row = (
                db.query(LeagueSettings)
                .filter(LeagueSettings.league_id == league.id)
                .with_for_update()
                .first()
            )
            if not settings_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
            timer_state = _get_or_create_draft_timer_state(db, draft_row.id)

            teams = get_ordered_draft_teams(db, league.id)
            if not teams:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no teams available for draft")

            existing_picks = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
            total_picks = _total_draft_picks_for_league(settings_row=settings_row, team_count=len(teams))
            if total_picks and existing_picks >= total_picks:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")

            round_number, round_pick, current_team = get_draft_pick_team_for_number(teams, existing_picks + 1)
            if current_team is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft cannot determine current team")

            if current_user.id not in {league.commissioner_user_id, current_team.owner_user_id}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not on the clock.")

            now_utc = datetime.now(timezone.utc)
            if draft_row.status == "scheduled":
                _start_scheduled_draft_on_first_pick(
                    draft_row=draft_row,
                    league=league,
                    timer_state=timer_state,
                    now_utc=now_utc,
                )

            current_pick_number = existing_picks + 1
            prep_remaining = _draft_pick_prep_remaining_seconds(
                draft_row=draft_row,
                timer_state=timer_state,
                now_utc=now_utc,
            )
            if prep_remaining > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Next pick begins in {prep_remaining}s.",
                )

            seconds_remaining = _seconds_remaining_for_current_pick(
                draft_row=draft_row,
                timer_state=timer_state,
                now_utc=now_utc,
            )
            if seconds_remaining is not None and seconds_remaining <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Pick clock expired. Auto-pick will submit this turn.",
                )

            player = db.query(Player).filter(Player.id == payload.player_id).with_for_update().first()
            if not player:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

            existing_player_pick = (
                db.query(DraftPick)
                .filter(DraftPick.draft_id == draft_row.id, DraftPick.player_id == player.id)
                .first()
            )
            if existing_player_pick:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already drafted")

            existing_roster_entry = (
                db.query(RosterEntry)
                .join(Team, Team.id == RosterEntry.team_id)
                .filter(Team.league_id == league.id, RosterEntry.player_id == player.id)
                .first()
            )
            if existing_roster_entry:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster")

            slot = assign_draft_roster_slot(db, settings_row, current_team.id, player.position)
            pick = DraftPick(
                draft_id=draft_row.id,
                team_id=current_team.id,
                player_id=player.id,
                made_by_user_id=current_user.id,
                round_number=round_number,
                round_pick=round_pick,
                overall_pick=current_pick_number,
                idempotency_key=resolved_idempotency_key,
            )
            db.add(pick)
            db.flush()

            db.add(
                RosterEntry(
                    league_id=league.id,
                    team_id=current_team.id,
                    player_id=player.id,
                    slot=slot,
                    status="active",
                )
            )
            db.flush()
            _remove_player_from_draft_queues(
                db,
                draft_id=draft_row.id,
                player_id=player.id,
            )

            league.status = "draft_live"
            _reset_draft_timer_for_next_pick(
                timer_state=timer_state,
                now_utc=now_utc,
                transition_seconds=0,
                draft_row=draft_row,
            )
            if is_draft_complete(current_pick_number, total_picks):
                _complete_draft(
                    draft_row=draft_row,
                    league=league,
                    timer_state=timer_state,
                    now_utc=now_utc,
                )

            db.add(draft_row)
            db.add(timer_state)
            db.add(league)
            _emit_draft_event(
                db,
                league_id=league.id,
                event_type="draft.pick.made",
                entity_type="draft_pick",
                entity_id=pick.id,
                payload={
                    "reason": "manual_pick",
                    "player_id": payload.player_id,
                    "overall_pick": current_pick_number,
                    "team_id": current_team.id,
                    "round_number": round_number,
                    "round_pick": round_pick,
                    "idempotency_key": resolved_idempotency_key,
                },
            )
            append_admin_action(
                db,
                league_id=league.id,
                actor_user_id=current_user.id,
                action_type="draft.pick.made",
                target_type="draft_pick",
                target_id=pick.id,
                metadata={
                    "player_id": payload.player_id,
                    "overall_pick": current_pick_number,
                    "team_id": current_team.id,
                    "round_number": round_number,
                    "round_pick": round_pick,
                },
            )
            _emit_draft_event(
                db,
                league_id=league.id,
                event_type="draft.room.updated",
                entity_type="draft_room",
                entity_id=draft_row.id,
                payload={"reason": "pick_committed"},
            )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if resolved_idempotency_key:
            existing_for_key = (
                db.query(DraftPick)
                .join(Draft, Draft.id == DraftPick.draft_id)
                .filter(
                    Draft.league_id == league.id,
                    DraftPick.idempotency_key == resolved_idempotency_key,
                )
                .first()
            )
            if existing_for_key and existing_for_key.player_id == payload.player_id:
                return get_draft_room_state(db, league, current_user)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_draft_conflict_detail(exc)) from exc

    return get_draft_room_state(db, league, current_user)


def update_draft_room_status(
    db: Session,
    *,
    league: League,
    payload: DraftRoomStatusUpdateRequest,
    current_user: User,
) -> DraftRoomRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    if draft_row.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")
    timer_state = _get_or_create_draft_timer_state(db, draft_row.id)
    now_utc = datetime.now(timezone.utc)

    def require_empty_draft_for_countdown() -> None:
        existing_pick_count = db.query(DraftPick.id).filter(DraftPick.draft_id == draft_row.id).count()
        if existing_pick_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot start countdown with existing picks. Use standalone mock drafts for practice.",
            )

    if payload.status == "paused":
        draft_row.status = "paused"
        _pause_draft_timer(timer_state=timer_state, now_utc=now_utc)
    elif payload.status == "active":
        if draft_row.status == "paused":
            draft_row.status = "live"
            draft_row.draft_datetime_utc = draft_row.draft_datetime_utc or now_utc
            if league.status != "post_draft":
                league.status = "draft_live"
            _start_or_resume_draft_timer(timer_state=timer_state, now_utc=now_utc)
        else:
            require_empty_draft_for_countdown()
            draft_row.status = "countdown"
            draft_row.draft_datetime_utc = now_utc
            if league.status != "post_draft":
                league.status = "draft_scheduled"
            _reset_draft_timer_for_next_pick(
                timer_state=timer_state,
                now_utc=now_utc,
                transition_seconds=0,
                draft_row=draft_row,
            )
    elif payload.status in {"filling", "lobby_open", "countdown"}:
        draft_row.status = payload.status
        if league.status != "post_draft":
            league.status = "draft_scheduled"
        if payload.status == "countdown":
            require_empty_draft_for_countdown()
            draft_row.draft_datetime_utc = now_utc
            _reset_draft_timer_for_next_pick(
                timer_state=timer_state,
                now_utc=now_utc,
                transition_seconds=0,
                draft_row=draft_row,
            )
        else:
            _pause_draft_timer(timer_state=timer_state, now_utc=now_utc)
    elif payload.status == "abandoned":
        draft_row.status = "abandoned"
        league.status = "post_draft"
        _pause_draft_timer(timer_state=timer_state, now_utc=now_utc)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported draft status transition")

    db.add(draft_row)
    db.add(timer_state)
    db.add(league)
    append_admin_action(
        db,
        league_id=league.id,
        actor_user_id=current_user.id,
        action_type="draft.status.changed",
        target_type="draft_room",
        target_id=draft_row.id,
        metadata={"status": draft_row.status},
    )
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.status.changed",
        entity_type="draft_room",
        entity_id=draft_row.id,
        payload={"status": draft_row.status},
    )
    db.commit()
    return get_draft_room_state(db, league, current_user)


def create_draft_pick(
    db: Session,
    league: League,
    payload: DraftPickCreate,
    current_user: User,
    *,
    idempotency_key: str | None = None,
) -> DraftRoomRead:
    return create_real_draft_pick(
        db,
        league,
        payload,
        current_user,
        idempotency_key=idempotency_key,
    )
