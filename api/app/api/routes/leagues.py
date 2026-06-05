import csv
import io
import logging
import math
import random
import re
import asyncio
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, case, func
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from api.app.api.deps import (
    get_current_user,
    get_league_or_404,
    require_commissioner,
    require_league_member,
)
from api.app.core.config import settings
from api.app.core.security import JWTError, JWTExpiredError, verify_access_token
from api.app.crud.league import delete_league, list_leagues
from api.app.db.session import SessionLocal, get_db
from api.app.models.draft import Draft
from api.app.models.draft_lobby_member import DraftLobbyMember
from api.app.models.draft_pick import DraftPick
from api.app.models.draft_team_queue_item import DraftTeamQueueItem
from api.app.models.draft_timer_state import DraftTimerState
from api.app.models.league import League
from api.app.models.league_invite import LeagueInvite
from api.app.models.league_member import LeagueMember
from api.app.models.league_settings import LeagueSettings
from api.app.models.league_week_state import LeagueWeekState
from api.app.models.matchup import Matchup
from api.app.models.notification import NotificationLog
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.scoring_run import ScoringRun
from api.app.models.team import Team
from api.app.models.user import User
from api.app.models.watchlist import Watchlist, WatchlistPlayer
from api.app.models.weekly_projection import WeeklyProjection
from api.app.schemas.audit import AdminActionListRead, AdminActionRead
from api.app.schemas.draft_room import (
    DraftAutoPickRequest,
    DraftHistoryEmailRequest,
    DraftHistoryEmailResponse,
    DraftHistoryResponse,
    DraftQueueAddRequest,
    DraftQueueItemRead,
    DraftQueueRead,
    DraftQueueReorderRequest,
    DraftEventEnvelopeRead,
    DraftLobbyReadyRequest,
    DraftSheetSyncRequest,
    DraftSheetSyncResponse,
    DraftPlayerImportRequest,
    DraftPlayerImportResponse,
    DraftPickCreate,
    DraftPracticeSetupRequest,
    DraftRoomPickRead,
    DraftRoomRead,
    DraftRoomSnapshotRead,
    DraftRoomStatusUpdateRequest,
    DraftSlotMoveRequest,
    DraftRoomTeamRead,
    DraftSheetSyncErrorRow,
    LeagueEventListRead,
)
from api.app.schemas.league import LeagueList
from api.app.schemas.league_flow import (
    DraftRead,
    DraftUpdate,
    MatchmakingJoinRequest,
    LeagueCreateRequest,
    LeagueCreateResponse,
    LeagueDetailRead,
    LeagueNewsList,
    LeagueWeekStateRead,
    LeagueWeekFinalizeResponse,
    LeagueWeekFinalizeStandingRead,
    LeagueWeekScoringRunRequest,
    LeagueWeekScoringRunResponse,
    LeagueWeekScoringRunHistoryResponse,
    LeagueWeekScoringRunHistoryRow,
    LeagueWeekMatchupScoreRead,
    LeagueWeekScoreRowRead,
    LeagueWeekStateUpdate,
    LeagueMemberRead,
    LeagueMembersList,
    LeaguePowerRankingList,
    LeaguePreview,
    LeagueScoreboardList,
    LeagueSettingsUpdate,
    LeagueWorkspaceRead,
    JoinByCodeRequest,
)
from api.app.services.league_flow import (
    FIXED_ROSTER_SLOTS,
    create_league,
    join_league as join_league_flow,
    regenerate_invite as regenerate_invite_flow,
    reschedule_draft as reschedule_draft_flow,
    update_league_settings as update_league_settings_flow,
)
from api.app.services.league_week_state import (
    get_or_create_week_state,
    transition_week_state,
)
from api.app.services.league_workspace import (
    build_league_news_items,
    build_power_rankings_rows,
    build_scoreboard_rows,
    build_league_workspace,
    get_league_detail,
)
from api.app.services.power4 import resolve_power4_school
from api.app.services.sportsdata_sync import (
    build_power4_player_class_lookup_from_cfbd,
    build_power4_player_class_lookup_from_sportsdata,
    normalize_player_class_label,
)
from api.app.services.admin_actions import append_admin_action, list_admin_actions
from api.app.services.draft_engine import (
    get_round_number,
    get_round_pick,
    get_snake_team_for_pick,
    get_total_picks,
    is_draft_complete,
)
from api.app.services.draft_history import generate_draft_history
from api.app.services.standings_engine import build_standings_snapshot
from api.app.services.week_scoring_runner import execute_week_scoring_run
from api.app.services.draft_realtime import draft_realtime_manager
from api.app.services import draft_service
from api.app.services.event_stream import (
    append_league_event,
    latest_league_event_seq,
    list_league_events_since,
)

router = APIRouter()
logger = logging.getLogger(__name__)

OFFENSE_DRAFT_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
DRAFT_POSITION_FULL_REASON = "You cannot draft this position because your roster has no available slot for it."
DRAFT_POSITION_LOCK_REASON = "Roster full for this position"
FLEX_ELIGIBLE_POSITIONS = {"RB", "WR", "TE"}
SUPERFLEX_ELIGIBLE_POSITIONS = {"QB", "RB", "WR", "TE"}
DRAFTABLE_SLOT_KEYS = {"QB", "RB", "WR", "TE", "K", "DEF", "FLEX", "SUPERFLEX", "BENCH"}
MATCHMAKING_TEAM_COUNTS = {4, 6, 8, 10, 12, 14, 16}
PUBLIC_JOINABLE_STATUSES = {"pre_draft", "matchmaking", "draft_scheduled"}
SHEET_HEADER_ALIASES = {
    "name": {"name", "player", "playername", "player_name"},
    "school": {"school", "team", "college", "program"},
    "position": {"position", "pos"},
    "class": {"class", "year", "classyear", "playerclass"},
    "adp": {"adp", "avgdraftposition", "average_draft_position"},
    "projected_fantasy_points": {
        "fantasyproj",
        "fantasyprojection",
        "fantasyprojectionpoints",
        "fantasy_proj",
        "projectedfantasypoints",
        "projected_fantasy_points",
        "projection",
        "projectedpoints",
        "projected_points",
        "seasonprojection",
        "season_projected_points",
    },
    "external_id": {"externalid", "sportsdataid", "playerid", "external_id"},
    "image_url": {"image", "imageurl", "headshot", "headshoturl", "image_url"},
}
SHEET_PROJECTION_STAT_ALIASES = {
    "comp": {"comp", "completions", "cmp", "comp."},
    "attempts": {"attempts", "atts", "att", "attempt"},
    "pass_yds": {"passyds", "pass_yds", "pass yards", "passyd", "pass yds"},
    "pass_tds": {"passtds", "pass_tds", "pass tds", "pass td"},
    "ints": {"ints", "int", "interceptions"},
    "rush_yds": {"rushyds", "rush_yds", "rush yds", "rush yards"},
    "rush_tds": {"rushtds", "rush_tds", "rush tds", "rush td"},
    "receptions": {"receptions", "rec", "recs"},
    "rec_yds": {"recyds", "rec_yds", "rec yds", "rec yards"},
    "rec_tds": {"rectds", "rec_tds", "rec tds", "rec td"},
    "fg": {"fg", "fieldgoals", "field goals"},
    "xp": {"xp", "extra points", "extra_points"},
}
SHEET_PROJECTION_STAT_KEYS = (
    "comp",
    "attempts",
    "pass_yds",
    "pass_tds",
    "ints",
    "rush_yds",
    "rush_tds",
    "receptions",
    "rec_yds",
    "rec_tds",
    "fg",
    "xp",
)
GOOGLE_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
SHEET_TAB_META_RE = re.compile(r'\[(\d+),0,\\"(\d+)\\",\[\{\\"1\\":\[\[0,0,\\"([^\\"]+)\\"')
POSITION_DEMAND_BONUS: dict[str, int] = {
    "QB": -24,
    "RB": 28,
    "WR": 28,
    "TE": 14,
    "K": -55,
}
FLEX_BONUS: dict[str, int] = {
    "QB": 0,
    "RB": 10,
    "WR": 10,
    "TE": 5,
    "K": 0,
}
REPLACEMENT_RANK_BY_POSITION: dict[str, int] = {
    "QB": 12,
    "RB": 30,
    "WR": 36,
    "TE": 12,
    "K": 12,
}
PROJECTION_WEIGHT = 1.00
VALUE_ABOVE_REPLACEMENT_WEIGHT = 0.15
DRAFT_AUTOPICKS_ENABLED = True
DRAFT_PICK_TRANSITION_SECONDS = 3
DRAFT_LOBBY_COUNTDOWN_SECONDS = 60
DRAFT_START_VISUAL_SECONDS = 2
DRAFT_CPU_AUTOPICK_BUFFER_SECONDS = 2
DRAFT_LOBBY_CONNECTED_TTL_SECONDS = 25
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
EVENT_SCHEMA_VERSION = 1

def _event_legacy_name(event_type: str) -> str:
    mapping = {
        "draft.room.snapshot": "draft_room_ready",
        "draft.room.updated": "draft_room_updated",
        "draft.pick.made": "draft_pick_made",
        "draft.player_pool.updated": "draft_player_pool_updated",
    }
    return mapping.get(event_type, event_type.replace(".", "_"))


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _draft_status_value(status_value: str | None) -> str:
    return DRAFT_STATUS_MAP.get((status_value or "").strip().lower(), "waiting")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_user_draft_team(
    db: Session,
    *,
    teams: list[Team],
    league: League,
    current_user: User,
    draft_status: str | None = None,
) -> Team:
    user_team = next((team for team in teams if team.owner_user_id == current_user.id), None)
    if user_team:
        return user_team
    if current_user.id == league.commissioner_user_id:
        if not teams:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no draft teams found")
        return teams[0]

    # Allow lobby/self-healing assignment for members who temporarily have no owned team
    # (for example after practice setup replaced teams with mock placeholders).
    # We also keep this enabled in live/paused to support late-join in mock/sandbox drafts.
    if (draft_status or "").lower() in {"filling", "lobby_open", "scheduled", "countdown", "live", "paused"}:
        unowned_team = next((team for team in teams if team.owner_user_id is None), None)
        if unowned_team is not None:
            display_name = (current_user.first_name or "").strip() or (current_user.email or "Manager").split("@")[0]
            unowned_team.owner_user_id = current_user.id
            unowned_team.owner_name = display_name
            current_name = (unowned_team.name or "").strip().lower()
            if not current_name or current_name.startswith("mock team") or current_name.startswith("auto team"):
                unowned_team.name = f"{display_name}'s Team"
            db.add(unowned_team)
            db.flush()
            return unowned_team

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no owned draft team found")


def _upsert_lobby_member(
    db: Session,
    *,
    draft_id: int,
    team_id: int,
    user_id: int,
    set_ready: bool | None = None,
) -> DraftLobbyMember:
    row = (
        db.query(DraftLobbyMember)
        .filter(
            DraftLobbyMember.draft_id == draft_id,
            DraftLobbyMember.user_id == user_id,
        )
        .with_for_update()
        .first()
    )
    now_utc = datetime.now(timezone.utc)
    if row is None:
        row = DraftLobbyMember(
            draft_id=draft_id,
            team_id=team_id,
            user_id=user_id,
            joined_at=now_utc,
            last_seen_at=now_utc,
            is_ready=bool(set_ready) if set_ready is not None else False,
        )
        db.add(row)
        db.flush()
        return row

    row.team_id = team_id
    row.last_seen_at = now_utc
    if set_ready is not None:
        row.is_ready = bool(set_ready)
    db.add(row)
    db.flush()
    return row


def _lobby_presence_summary(
    db: Session,
    *,
    draft_id: int,
    teams: list[Team],
    now_utc: datetime,
) -> tuple[dict[int, dict[str, bool]], int, int, int]:
    rows = (
        db.query(DraftLobbyMember)
        .filter(DraftLobbyMember.draft_id == draft_id)
        .all()
    )

    connected_cutoff = now_utc - timedelta(seconds=DRAFT_LOBBY_CONNECTED_TTL_SECONDS)
    by_team: dict[int, dict[str, bool]] = {
        team.id: {
            "joined": team.owner_user_id is None,
            "connected": team.owner_user_id is None,
            "ready": team.owner_user_id is None,
        }
        for team in teams
    }

    joined_count = 0
    connected_count = 0
    ready_count = 0
    for team in teams:
        if team.owner_user_id is None:
            joined_count += 1
            connected_count += 1
            ready_count += 1

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


def _broadcast_draft_event(
    league_id: int,
    event: str,
    payload: dict | None = None,
    *,
    event_id: str | None = None,
    event_type: str | None = None,
    seq: int | None = None,
    schema_version: int = EVENT_SCHEMA_VERSION,
    entity_type: str = "league",
    entity_id: int | None = None,
    occurred_at: datetime | None = None,
) -> None:
    async def _run() -> None:
        await draft_realtime_manager.broadcast(
            league_id,
            event=event,
            payload=payload,
            event_id=event_id,
            event_type=event_type,
            seq=seq,
            schema_version=schema_version,
            entity_type=entity_type,
            entity_id=entity_id,
            occurred_at=occurred_at,
        )

    try:
        asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()


def _event_row_to_envelope(event_row) -> DraftEventEnvelopeRead:
    return DraftEventEnvelopeRead(
        event_id=f"evt_{event_row.id}",
        event=_event_legacy_name(event_row.event_type),
        event_type=event_row.event_type,
        league_id=event_row.league_id,
        entity_type=event_row.entity_type,
        entity_id=event_row.entity_id,
        seq=event_row.id,
        schema_version=event_row.schema_version,
        at=event_row.occurred_at,
        payload=event_row.payload or {},
    )


def _emit_draft_event(
    db: Session,
    *,
    league_id: int,
    event_type: str,
    payload: dict | None = None,
    entity_type: str = "league",
    entity_id: int | None = None,
) -> DraftEventEnvelopeRead:
    row = append_league_event(
        db,
        league_id=league_id,
        event_type=event_type,
        payload=payload or {},
        entity_type=entity_type,
        entity_id=entity_id,
        schema_version=EVENT_SCHEMA_VERSION,
    )
    envelope = _event_row_to_envelope(row)
    if settings.realtime_immediate_broadcast_enabled:
        _broadcast_draft_event(
            league_id,
            event=envelope.event,
            event_type=envelope.event_type,
            event_id=envelope.event_id,
            seq=envelope.seq,
            schema_version=envelope.schema_version,
            entity_type=envelope.entity_type,
            entity_id=envelope.entity_id,
            occurred_at=envelope.at,
            payload=envelope.payload,
        )
    return envelope


def _normalize_sheet_tab_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _extract_sheet_id(sheet_url: str) -> str:
    match = GOOGLE_SHEET_ID_RE.search(sheet_url)
    if not match:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid Google Sheets URL")
    return match.group(1)


def _extract_gid(sheet_url: str, default_gid: str = "0") -> str:
    parsed = urllib.parse.urlparse(sheet_url)
    query = urllib.parse.parse_qs(parsed.query)
    if "gid" in query and query["gid"]:
        return str(query["gid"][0])
    fragment = parsed.fragment or ""
    if fragment.startswith("gid="):
        return fragment.replace("gid=", "", 1)
    return default_gid


def _download_google_sheet_csv(sheet_id: str, gid: str) -> list[dict[str, str]]:
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"unable to fetch Google Sheet CSV: {exc}",
        ) from exc

    reader = csv.DictReader(io.StringIO(body))
    rows = [dict(row or {}) for row in reader]
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sheet has no header row")
    return rows


def _fetch_sheet_tab_gid_map(sheet_id: str) -> dict[str, str]:
    edit_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    req = urllib.request.Request(edit_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"unable to fetch Google Sheet tab metadata: {exc}",
        ) from exc

    matches = SHEET_TAB_META_RE.findall(body)
    gid_map: dict[str, str] = {}
    for _index, gid, sheet_name in matches:
        key = _normalize_sheet_tab_name(sheet_name)
        if key:
            gid_map[key] = gid
    if not gid_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unable to resolve worksheet names to gid values from Google Sheet metadata",
        )
    return gid_map


def _download_google_sheet_csv_by_name(
    sheet_id: str,
    sheet_name: str,
    *,
    tab_gid_map: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    normalized_name = _normalize_sheet_tab_name(sheet_name)
    gid = (tab_gid_map or {}).get(normalized_name)
    if gid:
        return _download_google_sheet_csv(sheet_id, gid)

    encoded_name = urllib.parse.quote(sheet_name)
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet={encoded_name}"
    req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"unable to fetch Google Sheet tab '{sheet_name}' CSV: {exc}",
        ) from exc

    reader = csv.DictReader(io.StringIO(body))
    rows = [dict(row or {}) for row in reader]
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"sheet tab '{sheet_name}' has no header row",
        )
    return rows


def _resolve_header_mapping(row: dict[str, str]) -> dict[str, str]:
    source_headers = list(row.keys())
    normalized_to_original = {_normalized_header(header): header for header in source_headers}
    mapping: dict[str, str] = {}
    for canonical_name, aliases in SHEET_HEADER_ALIASES.items():
        for alias in aliases:
            original_header = normalized_to_original.get(_normalized_header(alias))
            if original_header:
                mapping[canonical_name] = original_header
                break
    return mapping


def _resolve_projection_stat_headers(row: dict[str, str]) -> dict[str, str]:
    source_headers = list(row.keys())
    normalized_to_original = {_normalized_header(header): header for header in source_headers}
    mapping: dict[str, str] = {}
    for stat_name, aliases in SHEET_PROJECTION_STAT_ALIASES.items():
        for alias in aliases:
            original_header = normalized_to_original.get(_normalized_header(alias))
            if original_header:
                mapping[stat_name] = original_header
                break
    return mapping


def _extract_projection_stats(raw: dict[str, str], projection_stat_headers: dict[str, str]) -> dict[str, float]:
    # Always return a complete projection stat payload for player cards.
    stats: dict[str, float] = {}
    for stat_name in SHEET_PROJECTION_STAT_KEYS:
        header = projection_stat_headers.get(stat_name)
        parsed = _safe_float(raw.get(header)) if header else None
        stats[stat_name] = float(parsed) if parsed is not None else 0.0
    return stats


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_player_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", (value or "").strip().lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return ""

    suffix_map = {
        "jr": "jr",
        "junior": "jr",
        "sr": "sr",
        "senior": "sr",
        "ii": "ii",
        "2": "ii",
        "2nd": "ii",
        "iii": "iii",
        "3": "iii",
        "3rd": "iii",
        "iv": "iv",
        "4": "iv",
        "4th": "iv",
    }
    parts = normalized.split(" ")
    if parts:
        last = parts[-1]
        if last in suffix_map:
            parts[-1] = suffix_map[last]
    return " ".join(parts)


def _normalized_name_parts(normalized_name: str) -> tuple[str, str] | None:
    parts = normalized_name.split(" ")
    if not parts:
        return None
    first = parts[0]
    last = parts[-1]
    if not first or not last:
        return None
    return first, last


def _resolve_projection_header(row: dict[str, str], mapping: dict[str, str]) -> str | None:
    # Prefer exact "FANTASY PROJ." style headers when available.
    source_headers = list(row.keys())
    exact_priority = [
        "FANTASY PROJ.",
        "FANTASY PROJ",
        "Fantasy Proj.",
        "Fantasy Proj",
    ]
    for header in exact_priority:
        if header in source_headers:
            return header
    return mapping.get("projected_fantasy_points")


def _apply_adp_formula(valid_rows: list[dict[str, object]]) -> None:
    def _scarcity_tier_bonus(position: str, position_rank: int) -> float:
        if position == "QB":
            if position_rank <= 3:
                return 18.0
            if position_rank <= 8:
                return 6.0
            return 0.0
        if position in {"RB", "WR"}:
            if position_rank <= 5:
                return 38.0
            if position_rank <= 12:
                return 24.0
            if position_rank <= 24:
                return 10.0
            return 0.0
        if position == "TE":
            if position_rank <= 3:
                return 30.0
            if position_rank <= 8:
                return 14.0
            return 0.0
        if position == "K":
            return -40.0
        return 0.0

    def _elite_gap_bonus(gap_to_next: float) -> float:
        if gap_to_next >= 70:
            return 40.0
        if gap_to_next >= 40:
            return 20.0
        return 0.0

    rows_by_position: dict[str, list[dict[str, object]]] = {}
    for row in valid_rows:
        position = str(row.get("position") or "").upper()
        rows_by_position.setdefault(position, []).append(row)

    adp_score_by_row_id: dict[int, float] = {}
    position_rank_by_row_id: dict[int, int] = {}
    replacement_level_by_row_id: dict[int, float] = {}
    value_above_replacement_by_row_id: dict[int, float] = {}
    elite_gap_by_row_id: dict[int, float] = {}
    scarcity_bonus_by_row_id: dict[int, float] = {}
    for position, rows in rows_by_position.items():
        rows.sort(
            key=lambda entry: (
                -float(entry.get("projected_fantasy_points") or 0),
                str(entry.get("name") or "").lower(),
            )
        )
        replacement_rank = REPLACEMENT_RANK_BY_POSITION.get(position, len(rows))
        replacement_index = max(0, min(len(rows), replacement_rank) - 1)
        replacement_level_projection = (
            float(rows[replacement_index].get("projected_fantasy_points") or 0.0)
            if rows
            else 0.0
        )

        for index, row in enumerate(rows, start=1):
            row_id = id(row)
            projected = float(row.get("projected_fantasy_points") or 0.0)
            next_projected = (
                float(rows[index].get("projected_fantasy_points") or 0.0)
                if index < len(rows)
                else projected
            )
            gap_to_next = max(0.0, projected - next_projected)
            value_above_replacement = projected - replacement_level_projection
            scarcity_bonus = _scarcity_tier_bonus(position, index)
            score = (
                (projected * PROJECTION_WEIGHT)
                + (value_above_replacement * VALUE_ABOVE_REPLACEMENT_WEIGHT)
                + float(POSITION_DEMAND_BONUS.get(position, 0))
                + scarcity_bonus
                + _elite_gap_bonus(gap_to_next)
                + float(FLEX_BONUS.get(position, 0))
            )
            adp_score_by_row_id[row_id] = score
            position_rank_by_row_id[row_id] = index
            replacement_level_by_row_id[row_id] = replacement_level_projection
            value_above_replacement_by_row_id[row_id] = value_above_replacement
            elite_gap_by_row_id[row_id] = gap_to_next
            scarcity_bonus_by_row_id[row_id] = scarcity_bonus

    provisional_sorted = sorted(
        valid_rows,
        key=lambda entry: (
            -float(adp_score_by_row_id.get(id(entry), 0)),
            -float(entry.get("projected_fantasy_points") or 0),
            str(entry.get("name") or "").lower(),
        ),
    )

    # Guardrail: preserve QB slotting from draft-value order, but ensure non-QB players
    # never invert by raw projection (higher projected non-QB always ahead of lower projected non-QB).
    non_qb_projection_sorted = sorted(
        (entry for entry in provisional_sorted if str(entry.get("position") or "").upper() != "QB"),
        key=lambda entry: (
            -float(entry.get("projected_fantasy_points") or 0),
            -float(adp_score_by_row_id.get(id(entry), 0)),
            str(entry.get("name") or "").lower(),
        ),
    )
    non_qb_iter = iter(non_qb_projection_sorted)
    all_rows_sorted: list[dict[str, object]] = []
    for entry in provisional_sorted:
        if str(entry.get("position") or "").upper() == "QB":
            all_rows_sorted.append(entry)
        else:
            all_rows_sorted.append(next(non_qb_iter))
    for rank, row in enumerate(all_rows_sorted, start=1):
        row["adp"] = float(rank)

    for rank, row in enumerate(all_rows_sorted[:25], start=1):
        row_id = id(row)
        logger.info(
            "draft_value_top25 rank=%s player=%s pos=%s fantasyProjection=%.2f valueAboveReplacement=%.2f scarcityBonus=%.2f draftValueScore=%.2f finalADP=%s",
            rank,
            str(row.get("name") or ""),
            str(row.get("position") or ""),
            float(row.get("projected_fantasy_points") or 0.0),
            value_above_replacement_by_row_id.get(row_id, 0.0),
            scarcity_bonus_by_row_id.get(row_id, 0.0),
            adp_score_by_row_id.get(row_id, 0.0),
            row.get("adp"),
        )


def _apply_projection_name_overrides(valid_rows: list[dict[str, object]]) -> None:
    hollywood_smothers_aliases = {
        _normalize_player_name("Hollywood Smothers"),
        _normalize_player_name("Hollylwood Smothers"),
        _normalize_player_name("Daylan Smothers"),
        _normalize_player_name("Daylan Hollywood Smothers"),
    }
    projection_bonus_points = 4.0
    for row in valid_rows:
        normalized_name = _normalize_player_name(str(row.get("name") or ""))
        if normalized_name not in hollywood_smothers_aliases:
            continue
        current_projection = float(row.get("projected_fantasy_points") or 0.0)
        boosted_projection = round(max(0.0, current_projection + projection_bonus_points), 2)
        row["projected_fantasy_points"] = boosted_projection
        logger.info(
            "sheet_sync_projection_override player=%s base=%.2f boosted=%.2f bonus=%.2f",
            row.get("name"),
            current_projection,
            boosted_projection,
            projection_bonus_points,
        )


def _get_or_create_global_watchlist(
    db: Session,
    *,
    current_user: User,
    watchlist_name: str,
) -> Watchlist:
    name = watchlist_name.strip() or "CFB Master Board"
    existing = (
        db.query(Watchlist)
        .filter(
            Watchlist.user_id == current_user.id,
            Watchlist.league_id.is_(None),
            Watchlist.name == name,
        )
        .first()
    )
    if existing:
        return existing

    created = Watchlist(user_id=current_user.id, league_id=None, name=name)
    db.add(created)
    db.flush()
    return created


def _replace_watchlist_players(
    db: Session,
    *,
    watchlist_id: int,
    player_ids: set[int],
) -> int:
    current_rows = (
        db.query(WatchlistPlayer)
        .filter(WatchlistPlayer.watchlist_id == watchlist_id)
        .all()
    )
    current_ids = {row.player_id for row in current_rows}
    add_ids = player_ids - current_ids
    remove_ids = current_ids - player_ids

    for player_id in add_ids:
        db.add(WatchlistPlayer(watchlist_id=watchlist_id, player_id=player_id))
    if remove_ids:
        (
            db.query(WatchlistPlayer)
            .filter(
                WatchlistPlayer.watchlist_id == watchlist_id,
                WatchlistPlayer.player_id.in_(remove_ids),
            )
            .delete(synchronize_session=False)
        )

    db.flush()
    return db.query(WatchlistPlayer).filter(WatchlistPlayer.watchlist_id == watchlist_id).count()


def _ordered_draft_teams(db: Session, league_id: int) -> list[Team]:
    return draft_service.get_ordered_draft_teams(db, league_id)


def _league_settings_meta(settings_row: LeagueSettings | None) -> dict:
    if not settings_row or not isinstance(settings_row.scoring_json, dict):
        return {}
    raw_meta = settings_row.scoring_json.get("__meta__")
    if isinstance(raw_meta, dict):
        return dict(raw_meta)
    return {}


def _draft_order_strategy_for_league(db: Session, league_id: int) -> str:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    meta = _league_settings_meta(settings_row)
    strategy = str(meta.get("draft_order_strategy") or "fixed").strip().lower()
    if strategy not in {"fixed", "random"}:
        return "fixed"
    return strategy


def _persist_draft_order(
    db: Session,
    *,
    league_id: int,
    ordered_team_ids: list[int],
    strategy: str | None = None,
) -> None:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings_row:
        return
    scoring_json = dict(settings_row.scoring_json or {})
    meta = _league_settings_meta(settings_row)
    meta["draft_order_team_ids"] = ordered_team_ids
    if strategy:
        meta["draft_order_strategy"] = strategy
    scoring_json["__meta__"] = meta
    settings_row.scoring_json = scoring_json
    db.add(settings_row)
    db.flush()


def _apply_draft_order_strategy(db: Session, *, league_id: int, strategy: str) -> list[int]:
    teams = sorted(
        db.query(Team).filter(Team.league_id == league_id).all(),
        key=lambda team: (team.created_at, team.id),
    )
    ordered_team_ids = [team.id for team in teams]
    if strategy == "random":
        random.shuffle(ordered_team_ids)
    _persist_draft_order(
        db,
        league_id=league_id,
        ordered_team_ids=ordered_team_ids,
        strategy=strategy,
    )
    return ordered_team_ids


def _update_matchmaking_draft_window_if_full(db: Session, league: League) -> None:
    if league.platform != "matchmaking" or league.status != "matchmaking":
        return

    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    if member_count < league.max_teams:
        return

    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        draft_row = Draft(
            league_id=league.id,
            draft_datetime_utc=datetime.now(timezone.utc) + timedelta(minutes=2),
            timezone="UTC",
            draft_type="snake",
            pick_timer_seconds=90,
            status="scheduled",
        )
        db.add(draft_row)
        db.flush()

    draft_row.status = "scheduled"
    draft_row.draft_datetime_utc = datetime.now(timezone.utc) + timedelta(minutes=2)
    league.status = "draft_scheduled"
    _apply_draft_order_strategy(db, league_id=league.id, strategy="random")
    db.add(draft_row)
    db.add(league)


def _ensure_draft_order_when_full(db: Session, league: League) -> None:
    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    if member_count < league.max_teams:
        return

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        return
    meta = _league_settings_meta(settings_row)
    existing_order = meta.get("draft_order_team_ids")
    if isinstance(existing_order, list) and len(existing_order) >= member_count:
        return

    strategy = _draft_order_strategy_for_league(db, league.id)
    _apply_draft_order_strategy(db, league_id=league.id, strategy=strategy)


def _draft_pick_team_for_number(teams: list[Team], pick_number: int) -> tuple[int, int, Team | None]:
    return draft_service.get_draft_pick_team_for_number(teams, pick_number)


def _get_or_create_draft_timer_state(db: Session, draft_id: int) -> DraftTimerState:
    return draft_service._get_or_create_draft_timer_state(db, draft_id)


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
    draft_service._reset_draft_timer_for_next_pick(
        timer_state=timer_state,
        now_utc=now_utc,
        transition_seconds=transition_seconds,
        draft_row=draft_row,
    )


def _complete_draft(
    *,
    draft_row: Draft,
    league: League,
    timer_state: DraftTimerState | None,
    now_utc: datetime,
) -> None:
    draft_service._complete_draft(
        draft_row=draft_row,
        league=league,
        timer_state=timer_state,
        now_utc=now_utc,
    )


def _normalize_summary_email(value: str | None) -> str | None:
    email = (value or "").strip().lower()
    if not email:
        return None
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid email address")
    return email


def _draft_pick_prep_remaining_seconds(
    *,
    draft_row: Draft,
    timer_state: DraftTimerState | None,
    now_utc: datetime,
) -> int:
    return draft_service._draft_pick_prep_remaining_seconds(
        draft_row=draft_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )


@dataclass(frozen=True)
class DraftPositionFit:
    can_draft: bool
    reason: str | None = None
    destination_slot: str | None = None


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
    canonical: dict[str, int] = {
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
        if limit <= 0:
            continue
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


def _draftable_roster_rounds_from_slots(roster_slots: dict | None) -> int:
    slot_limits = _build_canonical_slot_limits(roster_slots)
    return sum(int(slot_limits.get(slot, 0)) for slot in DRAFTABLE_SLOT_KEYS)


def can_draft_position(
    player_position: str,
    roster: object,
    roster_settings: LeagueSettings | dict,
) -> DraftPositionFit:
    normalized_position = _normalize_position(player_position)
    if not normalized_position:
        return DraftPositionFit(
            can_draft=False,
            reason="invalid player position",
            destination_slot=None,
        )

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
    if (
        normalized_position in FLEX_ELIGIBLE_POSITIONS
        and flex_limit
        and current_counts.get("FLEX", 0) < flex_limit
    ):
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

    return DraftPositionFit(
        can_draft=False,
        reason=DRAFT_POSITION_FULL_REASON,
        destination_slot=None,
    )


def _team_roster_entries(db: Session, team_id: int) -> list[RosterEntry]:
    return db.query(RosterEntry).filter(RosterEntry.team_id == team_id).all()


def _assign_roster_slot(
    db: Session,
    settings_row: LeagueSettings,
    team_id: int,
    player_position: str,
) -> str:
    return draft_service.assign_draft_roster_slot(db, settings_row, team_id, player_position)


def _ordered_autopick_candidates(
    db: Session,
    *,
    draft_id: int,
    league_id: int,
    limit: int = 300,
) -> list[Player]:
    drafted_player_ids_subquery = db.query(DraftPick.player_id).filter(DraftPick.draft_id == draft_id)
    rostered_player_ids_subquery = db.query(RosterEntry.player_id).filter(RosterEntry.league_id == league_id)

    # Autopicks should mirror the top of the draft board:
    # 1) lowest ADP first (best available),
    # 2) then highest projection for deterministic ties.
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


def _normalize_queue_priorities(
    db: Session,
    *,
    draft_id: int,
    team_id: int,
) -> list[DraftTeamQueueItem]:
    rows = (
        db.query(DraftTeamQueueItem)
        .filter(
            DraftTeamQueueItem.draft_id == draft_id,
            DraftTeamQueueItem.team_id == team_id,
        )
        .order_by(DraftTeamQueueItem.priority.asc(), DraftTeamQueueItem.id.asc())
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


def _remove_player_from_draft_queues(
    db: Session,
    *,
    draft_id: int,
    player_id: int,
) -> None:
    draft_service._remove_player_from_draft_queues(db, draft_id=draft_id, player_id=player_id)


def _queued_autopick_candidate(
    db: Session,
    *,
    draft_id: int,
    league_id: int,
    team_id: int,
) -> Player | None:
    drafted_player_ids_subquery = db.query(DraftPick.player_id).filter(DraftPick.draft_id == draft_id)
    rostered_player_ids_subquery = db.query(RosterEntry.player_id).filter(RosterEntry.league_id == league_id)
    queue_rows = _normalize_queue_priorities(db, draft_id=draft_id, team_id=team_id)
    for queue_row in queue_rows:
        player = (
            db.query(Player)
            .filter(Player.id == queue_row.player_id)
            .filter(~Player.id.in_(drafted_player_ids_subquery))
            .filter(~Player.id.in_(rostered_player_ids_subquery))
            .first()
        )
        if player:
            return player
    return None


def _queue_item_to_read(
    *,
    queue_item: DraftTeamQueueItem,
    player: Player,
) -> DraftQueueItemRead:
    return DraftQueueItemRead(
        id=queue_item.id,
        priority=int(queue_item.priority),
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


def _draft_queue_state(
    db: Session,
    *,
    league: League,
    draft_row: Draft,
    team_id: int,
) -> DraftQueueRead:
    queue_rows = _normalize_queue_priorities(db, draft_id=draft_row.id, team_id=team_id)

    data: list[DraftQueueItemRead] = []
    removed_any = False
    for row in queue_rows:
        player = db.get(Player, row.player_id)
        if player is None:
            db.delete(row)
            removed_any = True
            continue
        drafted = (
            db.query(DraftPick.id)
            .filter(DraftPick.draft_id == draft_row.id, DraftPick.player_id == player.id)
            .first()
        )
        rostered = (
            db.query(RosterEntry.id)
            .filter(RosterEntry.league_id == league.id, RosterEntry.player_id == player.id)
            .first()
        )
        if drafted or rostered:
            db.delete(row)
            removed_any = True
            continue
        data.append(_queue_item_to_read(queue_item=row, player=player))

    if removed_any:
        db.flush()
        queue_rows = _normalize_queue_priorities(db, draft_id=draft_row.id, team_id=team_id)
        data = []
        for row in queue_rows:
            player = db.get(Player, row.player_id)
            if player:
                data.append(_queue_item_to_read(queue_item=row, player=player))

    return DraftQueueRead(
        draft_id=draft_row.id,
        league_id=league.id,
        team_id=team_id,
        count=len(data),
        data=data,
    )


def _total_draft_picks_for_league(*, settings_row: LeagueSettings, team_count: int) -> int:
    return draft_service._total_draft_picks_for_league(settings_row=settings_row, team_count=team_count)


def _total_roster_slot_rounds(*, settings_row: LeagueSettings) -> int:
    return draft_service._total_roster_slot_rounds(settings_row=settings_row)


def _seconds_remaining_for_current_pick(
    *,
    draft_row: Draft,
    timer_state: DraftTimerState | None,
    now_utc: datetime,
    current_team: Team | None = None,
    current_pick_number: int | None = None,
) -> int | None:
    return draft_service._seconds_remaining_for_current_pick(
        draft_row=draft_row,
        timer_state=timer_state,
        now_utc=now_utc,
    )


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
        current_team=None,
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


def _autopick_timed_out_current_team(
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

        teams = _ordered_draft_teams(db, league.id)
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

        round_number, round_pick, current_team = _draft_pick_team_for_number(teams, existing_picks + 1)
        if current_team is None:
            return False

        current_pick_number = existing_picks + 1
        seconds_remaining = _seconds_remaining_for_current_pick(
            draft_row=draft_row,
            timer_state=timer_state,
            now_utc=now_utc,
            current_team=current_team,
            current_pick_number=current_pick_number,
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

        # Timeout autopicks must mirror the draft board directly:
        # pick the top available ADP player, and only fall through when
        # that player's position cannot fit any valid slot for this roster.
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

        db.add(
            DraftPick(
                draft_id=draft_row.id,
                team_id=current_team.id,
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


def _draft_room_state(db: Session, league: League, current_user: User) -> DraftRoomRead:
    return draft_service.get_draft_room_state(db, league, current_user)



def _normalize_position(value: str) -> str:
    normalized = (value or "").strip().upper()
    if not normalized:
        return ""

    # Accept depth-chart labels like QB1 / RB2 / WR3 and keep base position.
    if normalized in {"DST", "D/ST"} or normalized.startswith("DEF"):
        return "DEF"

    for base in ("QB", "RB", "WR", "TE", "K"):
        if normalized.startswith(base):
            return base

    compact = re.sub(r"[^A-Z]", "", normalized)
    position_map = {
        "PK": "K",
        "HB": "RB",
        "FB": "RB",
        "QB": "QB",
        "RB": "RB",
        "WR": "WR",
        "TE": "TE",
        "K": "K",
        "DST": "DEF",
        "DEF": "DEF",
    }
    for key, mapped in position_map.items():
        if compact.startswith(key):
            return mapped
    return compact


def _get_user_from_ws_token(db: Session, token: str | None) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")
    try:
        payload = verify_access_token(token)
    except JWTExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired access token") from exc
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid access token") from exc

    user_id_raw = payload.get("sub")
    try:
        user_id = int(user_id_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid access token") from exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid access token")
    return user


def _next_mock_team_name(existing_names: set[str], prefix: str, start_index: int) -> tuple[str, int]:
    index = max(1, start_index)
    while True:
        candidate = f"{prefix} {index}"
        if candidate not in existing_names:
            return candidate, index + 1
        index += 1


def _setup_draft_practice(
    db: Session,
    *,
    league: League,
    payload: DraftPracticeSetupRequest,
    current_user: User,
) -> None:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        draft_row = Draft(
            league_id=league.id,
            draft_datetime_utc=datetime.now(timezone.utc),
            timezone="UTC",
            draft_type="snake",
            pick_timer_seconds=90,
            status="scheduled",
        )
        db.add(draft_row)
        db.flush()

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    settings_row.roster_slots_json = FIXED_ROSTER_SLOTS.copy()
    settings_row.superflex_enabled = False
    settings_row.kicker_enabled = True
    settings_row.defense_enabled = False
    db.add(settings_row)

    target_count = payload.team_count or league.max_teams
    if target_count > league.max_teams:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"team_count cannot exceed league max teams ({league.max_teams})",
        )

    teams = _ordered_draft_teams(db, league.id)
    owned_teams = [team for team in teams if team.owner_user_id is not None]
    if target_count < len(owned_teams):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"team_count must be at least number of owner teams ({len(owned_teams)})",
        )

    if payload.reset_existing:
        db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).delete(synchronize_session=False)
        db.query(RosterEntry).filter(RosterEntry.league_id == league.id).delete(synchronize_session=False)
        for team in teams:
            if team.owner_user_id is None:
                db.delete(team)
        db.flush()
        teams = _ordered_draft_teams(db, league.id)

    teams = _ordered_draft_teams(db, league.id)

    manager_owner_name = (current_user.first_name or "").strip() or (current_user.email or "manager").split("@")[0]
    manager_team = next((team for team in teams if team.owner_user_id == current_user.id), None)
    if manager_team is None:
        manager_team = next((team for team in teams if team.owner_user_id == league.commissioner_user_id), None)
    if manager_team is None:
        manager_team = teams[0] if teams else None

    if manager_team is None:
        manager_team = Team(
            league_id=league.id,
            name="Manager 1",
            owner_name=manager_owner_name,
            owner_user_id=current_user.id,
        )
        db.add(manager_team)
        db.flush()
        teams.append(manager_team)

    for team in teams:
        if team.id == manager_team.id:
            team.owner_user_id = current_user.id
            team.owner_name = manager_owner_name
            team.name = "Manager 1"
        else:
            team.owner_user_id = None
            team.owner_name = None
        db.add(team)
    db.flush()

    teams = _ordered_draft_teams(db, league.id)
    mock_teams = [team for team in teams if team.owner_user_id is None]
    if len(teams) > target_count:
        removable_count = len(teams) - target_count
        if removable_count > len(mock_teams):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot reduce teams below assigned owner teams",
            )
        for team in sorted(mock_teams, key=lambda row: (row.created_at, row.id), reverse=True)[:removable_count]:
            db.delete(team)
        db.flush()
        teams = _ordered_draft_teams(db, league.id)

    prefix = payload.mock_team_prefix.strip() or "Auto Manager"
    existing_names = {"Manager 1"}
    next_index = 2

    for mock_team in sorted((team for team in teams if team.id != manager_team.id), key=lambda row: (row.created_at, row.id)):
        team_name, next_index = _next_mock_team_name(existing_names, prefix, next_index)
        mock_number = team_name.split(" ")[-1]
        mock_team.name = team_name
        mock_team.owner_name = f"Auto Manager {mock_number}"
        mock_team.owner_user_id = None
        db.add(mock_team)
        existing_names.add(team_name)

    while len(teams) < target_count:
        team_name, next_index = _next_mock_team_name(existing_names, prefix, next_index)
        mock_number = team_name.split(" ")[-1]
        mock_team = Team(
            league_id=league.id,
            name=team_name,
            owner_name=f"Auto Manager {mock_number}",
            owner_user_id=None,
        )
        db.add(mock_team)
        db.flush()
        teams.append(mock_team)
        existing_names.add(team_name)

    ordered_team_ids = [team.id for team in _ordered_draft_teams(db, league.id)]
    strategy = _draft_order_strategy_for_league(db, league.id)
    if strategy == "random":
        random.shuffle(ordered_team_ids)
    _persist_draft_order(
        db,
        league_id=league.id,
        ordered_team_ids=ordered_team_ids,
        strategy=strategy,
    )

    draft_row.status = "countdown" if payload.start_now else "lobby_open"
    timer_state = _get_or_create_draft_timer_state(db, draft_row.id)
    now_utc = datetime.now(timezone.utc)
    if payload.start_now:
        draft_row.draft_datetime_utc = now_utc
        if league.status != "post_draft":
            league.status = "draft_scheduled"
        _reset_draft_timer_for_next_pick(timer_state=timer_state, now_utc=now_utc, transition_seconds=0, draft_row=draft_row)
    else:
        draft_row.draft_datetime_utc = now_utc
        if league.status not in {"draft_scheduled", "draft_live"}:
            league.status = "draft_scheduled"
        timer_state.timer_started_at = None
        timer_state.paused_at = None
        timer_state.paused_total_seconds = 0
        timer_state.last_tick_at = now_utc
        timer_state.state_version += 1

    db.add(draft_row)
    db.add(timer_state)
    db.add(league)
    db.commit()


def _import_draft_player_pool(
    db: Session,
    *,
    payload: DraftPlayerImportRequest,
    collected_player_ids: set[int] | None = None,
    unmatched_player_names: list[str] | None = None,
    matched_existing_counter: list[int] | None = None,
) -> DraftPlayerImportResponse:
    rows = payload.rows
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rows are required")

    incoming_external_ids = {
        row.external_id.strip()
        for row in rows
        if row.external_id and row.external_id.strip()
    }
    incoming_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        incoming_keys.add(
            (
                row.name.strip().lower(),
                _normalize_position(row.position),
                row.school.strip().lower(),
            )
        )

    created = 0
    updated = 0
    for row in rows:
        name = row.name.strip()
        school = row.school.strip()
        position = _normalize_position(row.position)
        if not name or not school or not position:
            continue
        if position not in OFFENSE_DRAFT_POSITIONS:
            continue

        existing: Player | None = None
        matched_existing = False
        if row.external_id and row.external_id.strip():
            existing = (
                db.query(Player)
                .filter(Player.external_id == row.external_id.strip())
                .first()
            )
            if existing:
                matched_existing = True
        if not existing:
            existing = (
                db.query(Player)
                .filter(
                    Player.name == name,
                    Player.position == position,
                    Player.school == school,
                )
                .first()
            )
            if existing:
                matched_existing = True
        if not existing:
            normalized_name = _normalize_player_name(name)
            school_lower = school.lower()
            same_school_candidates = (
                db.query(Player)
                .filter(Player.position == position)
                .filter(func.lower(Player.school) == school_lower)
                .all()
            )
            for candidate in same_school_candidates:
                if _normalize_player_name(candidate.name) == normalized_name:
                    existing = candidate
                    matched_existing = True
                    break
        if not existing:
            normalized_name = _normalize_player_name(name)
            position_candidates = db.query(Player).filter(Player.position == position).all()
            normalized_matches = [
                candidate for candidate in position_candidates if _normalize_player_name(candidate.name) == normalized_name
            ]
            if len(normalized_matches) == 1:
                existing = normalized_matches[0]
                matched_existing = True

        if existing:
            existing.name = name
            existing.position = position
            existing.school = school
            existing.image_url = row.image_url
            existing.player_class = row.player_class.strip() if row.player_class else None
            existing.sheet_adp = row.adp
            existing.sheet_projected_season_points = row.projected_fantasy_points
            existing.sheet_projection_stats = row.projection_stats
            if row.external_id and row.external_id.strip():
                existing.external_id = row.external_id.strip()
            if row.projected_fantasy_points is not None:
                existing.sheet_synced_at = datetime.now(timezone.utc)
            db.add(existing)
            db.flush()
            if collected_player_ids is not None:
                collected_player_ids.add(existing.id)
            if matched_existing_counter is not None:
                matched_existing_counter[0] += 1
            updated += 1
            continue

        created_player = Player(
            external_id=row.external_id.strip() if row.external_id else None,
            name=name,
            position=position,
            school=school,
            image_url=row.image_url,
            player_class=row.player_class.strip() if row.player_class else None,
            sheet_adp=row.adp,
            sheet_projected_season_points=row.projected_fantasy_points,
            sheet_projection_stats=row.projection_stats,
            sheet_synced_at=datetime.now(timezone.utc) if row.projected_fantasy_points is not None else None,
        )
        db.add(created_player)
        db.flush()
        if collected_player_ids is not None:
            collected_player_ids.add(created_player.id)
        if unmatched_player_names is not None:
            unmatched_player_names.append(name)
        created += 1

    removed = 0
    if payload.replace_mode == "replace_offense_pool":
        rostered_player_ids = {
            player_id
            for (player_id,) in db.query(RosterEntry.player_id).distinct().all()
        }
        candidates = db.query(Player).filter(Player.position.in_(tuple(OFFENSE_DRAFT_POSITIONS))).all()
        for player in candidates:
            if player.id in rostered_player_ids:
                continue
            key = (
                player.name.strip().lower(),
                _normalize_position(player.position),
                player.school.strip().lower(),
            )
            external_id = (player.external_id or "").strip()
            keep_by_external = bool(external_id and external_id in incoming_external_ids)
            keep_by_key = key in incoming_keys
            if keep_by_external or keep_by_key:
                continue
            db.delete(player)
            removed += 1

    db.commit()
    return DraftPlayerImportResponse(
        received=len(rows),
        created=created,
        updated=updated,
        removed=removed,
    )


def _sync_sheet_to_draft_and_watchlist(
    db: Session,
    *,
    payload: DraftSheetSyncRequest,
    current_user: User,
    season_year: int | None = None,
) -> DraftSheetSyncResponse:
    sheet_url = str(payload.sheet_url)
    sheet_id = _extract_sheet_id(sheet_url)
    sheet_sources: list[tuple[str, list[dict[str, str]]]] = []
    worksheet_names = [name.strip() for name in payload.worksheet_names if name and name.strip()]
    if worksheet_names:
        tab_gid_map = _fetch_sheet_tab_gid_map(sheet_id)
        for worksheet_name in worksheet_names:
            rows = _download_google_sheet_csv_by_name(sheet_id, worksheet_name, tab_gid_map=tab_gid_map)
            sheet_sources.append((worksheet_name, rows))
    else:
        gid = payload.worksheet_gid or _extract_gid(sheet_url, default_gid="0")
        rows = _download_google_sheet_csv(sheet_id, gid)
        sheet_sources.append((f"gid:{gid}", rows))

    total_received_rows = sum(len(rows) for _, rows in sheet_sources)
    if total_received_rows == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sheet has no data rows")

    class_lookup: dict[tuple[str, str, str], str] = {}
    class_lookup_by_name_pos: dict[tuple[str, str], str] = {}
    class_lookup_by_school_pos_last_initial: dict[tuple[str, str, str, str], str] = {}
    cfbd_class_lookup: dict[tuple[str, str, str], str] = {}
    cfbd_class_lookup_by_name_pos: dict[tuple[str, str], str] = {}
    cfbd_class_lookup_by_school_pos_last_initial: dict[tuple[str, str, str, str], str] = {}
    if settings.sportsdata_enabled:
        try:
            class_lookup = build_power4_player_class_lookup_from_sportsdata()
            collision_keys: set[tuple[str, str]] = set()
            fuzzy_collision_keys: set[tuple[str, str, str, str]] = set()
            for (normalized_name, normalized_position, _school), class_label in class_lookup.items():
                fallback_key = (normalized_name, normalized_position)
                existing = class_lookup_by_name_pos.get(fallback_key)
                if existing is None:
                    class_lookup_by_name_pos[fallback_key] = class_label
                elif existing != class_label:
                    collision_keys.add(fallback_key)
            for (normalized_name, normalized_position, school), class_label in class_lookup.items():
                name_parts = _normalized_name_parts(normalized_name)
                if not name_parts:
                    continue
                first, last = name_parts
                fuzzy_key = (school, normalized_position, last, first[:1])
                existing = class_lookup_by_school_pos_last_initial.get(fuzzy_key)
                if existing is None:
                    class_lookup_by_school_pos_last_initial[fuzzy_key] = class_label
                elif existing != class_label:
                    fuzzy_collision_keys.add(fuzzy_key)
            for key in collision_keys:
                class_lookup_by_name_pos.pop(key, None)
            for key in fuzzy_collision_keys:
                class_lookup_by_school_pos_last_initial.pop(key, None)
            logger.info(
                "sheet_sync_class_lookup_loaded sportsdata_rows=%s fallback_rows=%s fuzzy_rows=%s",
                len(class_lookup),
                len(class_lookup_by_name_pos),
                len(class_lookup_by_school_pos_last_initial),
            )
        except Exception as exc:
            logger.warning("sheet_sync_class_lookup_failed reason=%s", exc)
    if settings.cfbd_api_key:
        try:
            cfbd_class_lookup = build_power4_player_class_lookup_from_cfbd(target_season=season_year)
            collision_keys: set[tuple[str, str]] = set()
            fuzzy_collision_keys: set[tuple[str, str, str, str]] = set()
            for (normalized_name, normalized_position, _school), class_label in cfbd_class_lookup.items():
                fallback_key = (normalized_name, normalized_position)
                existing = cfbd_class_lookup_by_name_pos.get(fallback_key)
                if existing is None:
                    cfbd_class_lookup_by_name_pos[fallback_key] = class_label
                elif existing != class_label:
                    collision_keys.add(fallback_key)
            for (normalized_name, normalized_position, school), class_label in cfbd_class_lookup.items():
                name_parts = _normalized_name_parts(normalized_name)
                if not name_parts:
                    continue
                first, last = name_parts
                fuzzy_key = (school, normalized_position, last, first[:1])
                existing = cfbd_class_lookup_by_school_pos_last_initial.get(fuzzy_key)
                if existing is None:
                    cfbd_class_lookup_by_school_pos_last_initial[fuzzy_key] = class_label
                elif existing != class_label:
                    fuzzy_collision_keys.add(fuzzy_key)
            for key in collision_keys:
                cfbd_class_lookup_by_name_pos.pop(key, None)
            for key in fuzzy_collision_keys:
                cfbd_class_lookup_by_school_pos_last_initial.pop(key, None)
            logger.info(
                "sheet_sync_cfbd_class_lookup_loaded rows=%s fallback_rows=%s fuzzy_rows=%s season=%s",
                len(cfbd_class_lookup),
                len(cfbd_class_lookup_by_name_pos),
                len(cfbd_class_lookup_by_school_pos_last_initial),
                season_year,
            )
        except Exception as exc:
            logger.warning("sheet_sync_cfbd_class_lookup_failed reason=%s", exc)

    valid_rows: list = []
    invalid_rows: list[DraftSheetSyncErrorRow] = []

    for source_name, raw_rows in sheet_sources:
        if not raw_rows:
            continue
        header_mapping = _resolve_header_mapping(raw_rows[0])
        projection_stat_headers = _resolve_projection_stat_headers(raw_rows[0])
        projection_header = _resolve_projection_header(raw_rows[0], header_mapping)
        required = ["name", "school", "position"]
        missing = [column for column in required if column not in header_mapping]
        if missing or not projection_header:
            missing_columns = list(missing)
            if not projection_header:
                missing_columns.append("FANTASY PROJ.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"sheet source '{source_name}' is missing required columns: {', '.join(missing_columns)}",
            )

        adp_header = header_mapping.get("adp")
        class_header = header_mapping.get("class")

        for index, raw in enumerate(raw_rows, start=2):
            name = (raw.get(header_mapping["name"]) or "").strip()
            school = (raw.get(header_mapping["school"]) or "").strip()
            position = _normalize_position(raw.get(header_mapping["position"]) or "")
            player_class = normalize_player_class_label((raw.get(class_header or "") or "").strip())
            normalized_name = _normalize_player_name(name)
            canonical_school = resolve_power4_school(school) or school
            class_source = "sheet"
            if not player_class and normalized_name and position and canonical_school:
                direct_lookup_key = (normalized_name, position, canonical_school)
                player_class = class_lookup.get(direct_lookup_key)
                if player_class:
                    class_source = "sportsdata_direct"
                else:
                    fallback_lookup_key = (normalized_name, position)
                    player_class = class_lookup_by_name_pos.get(fallback_lookup_key)
                    if player_class:
                        class_source = "sportsdata_fallback"
                    else:
                        name_parts = _normalized_name_parts(normalized_name)
                        if name_parts:
                            first, last = name_parts
                            fuzzy_key = (canonical_school, position, last, first[:1])
                            player_class = class_lookup_by_school_pos_last_initial.get(fuzzy_key)
                            if player_class:
                                class_source = "sportsdata_fuzzy"
            if not player_class and normalized_name and position and canonical_school:
                direct_lookup_key = (normalized_name, position, canonical_school)
                player_class = cfbd_class_lookup.get(direct_lookup_key)
                if player_class:
                    class_source = "cfbd_direct"
                else:
                    fallback_lookup_key = (normalized_name, position)
                    player_class = cfbd_class_lookup_by_name_pos.get(fallback_lookup_key)
                    if player_class:
                        class_source = "cfbd_fallback"
                    else:
                        name_parts = _normalized_name_parts(normalized_name)
                        if name_parts:
                            first, last = name_parts
                            fuzzy_key = (canonical_school, position, last, first[:1])
                            player_class = cfbd_class_lookup_by_school_pos_last_initial.get(fuzzy_key)
                            if player_class:
                                class_source = "cfbd_fuzzy"
            sheet_adp_input = _safe_float(raw.get(adp_header or "")) if adp_header else None
            projected_raw = raw.get(projection_header or "")
            projected = _safe_float(projected_raw)
            projection_stats = _extract_projection_stats(raw, projection_stat_headers)
            external_id = (raw.get(header_mapping.get("external_id", "")) or "").strip() or None
            image_url = (raw.get(header_mapping.get("image_url", "")) or "").strip() or None

            logger.info(
                "sheet_row source=%s row=%s player=%s team=%s position=%s class=%s class_source=%s fantasy_proj_raw=%s fantasy_proj=%s adp_input=%s",
                source_name,
                index,
                name,
                school,
                position,
                player_class,
                class_source,
                projected_raw,
                projected,
                sheet_adp_input,
            )

            if not name:
                logger.warning("sheet_row_invalid source=%s row=%s reason=missing player name raw=%s", source_name, index, raw)
                invalid_rows.append(DraftSheetSyncErrorRow(row_number=index, reason=f"{source_name}: missing player name", raw=raw))
                continue
            if not school:
                logger.warning("sheet_row_invalid source=%s row=%s reason=missing school raw=%s", source_name, index, raw)
                invalid_rows.append(DraftSheetSyncErrorRow(row_number=index, reason=f"{source_name}: missing school", raw=raw))
                continue
            if position not in OFFENSE_DRAFT_POSITIONS:
                logger.warning("sheet_row_invalid source=%s row=%s reason=invalid position value=%s raw=%s", source_name, index, position, raw)
                invalid_rows.append(
                    DraftSheetSyncErrorRow(
                        row_number=index,
                        reason=f"{source_name}: invalid position '{position}'",
                        raw=raw,
                    )
                )
                continue
            if projected is None:
                logger.warning(
                    "sheet_row_invalid source=%s row=%s reason=invalid FANTASY PROJ. projection_raw=%s raw=%s",
                    source_name,
                    index,
                    projected_raw,
                    raw,
                )
                invalid_rows.append(
                    DraftSheetSyncErrorRow(
                        row_number=index,
                        reason=f"{source_name}: invalid FANTASY PROJ. value",
                        raw=raw,
                    )
                )
                continue

            valid_rows.append(
                {
                    "external_id": external_id,
                    "name": name,
                    "position": position,
                    "school": school,
                    "image_url": image_url,
                    "player_class": player_class or None,
                    "adp": sheet_adp_input,
                    "projected_fantasy_points": projected,
                    "projection_stats": projection_stats,
                }
            )

    _apply_projection_name_overrides(valid_rows)
    _apply_adp_formula(valid_rows)

    wr_rows = sorted(
        [row for row in valid_rows if str(row.get("position") or "").upper() == "WR"],
        key=lambda row: (-float(row.get("projected_fantasy_points") or 0.0), str(row.get("name") or "").lower()),
    )
    wr_projection_rank_by_name: dict[str, int] = {}
    for index, row in enumerate(wr_rows, start=1):
        wr_projection_rank_by_name[_normalize_player_name(str(row.get("name") or ""))] = index

    wr_rows_by_adp = sorted(
        [row for row in valid_rows if str(row.get("position") or "").upper() == "WR"],
        key=lambda row: (float(row.get("adp") or 9999.0), -float(row.get("projected_fantasy_points") or 0.0), str(row.get("name") or "").lower()),
    )
    wr_adp_rank_by_name: dict[str, int] = {}
    for index, row in enumerate(wr_rows_by_adp, start=1):
        wr_adp_rank_by_name[_normalize_player_name(str(row.get("name") or ""))] = index

    cam_key = _normalize_player_name("Cam Coleman")
    ryan_aliases = [
        _normalize_player_name("Ryan Williams"),
        _normalize_player_name("Ryan Coleman-Williams"),
    ]
    cam_projection_rank = wr_projection_rank_by_name.get(cam_key)
    ryan_projection_rank = next(
        (wr_projection_rank_by_name.get(alias) for alias in ryan_aliases if alias in wr_projection_rank_by_name),
        None,
    )
    cam_adp_rank = wr_adp_rank_by_name.get(cam_key)
    ryan_adp_rank = next(
        (wr_adp_rank_by_name.get(alias) for alias in ryan_aliases if alias in wr_adp_rank_by_name),
        None,
    )
    if cam_projection_rank is None or cam_projection_rank > 5:
        logger.warning(
            "sheet_sync_wr_rank_guardrail_failed player=Cam Coleman projection_rank=%s expected_max=5",
            cam_projection_rank,
        )
    if ryan_projection_rank is None or ryan_projection_rank > 10:
        logger.warning(
            "sheet_sync_wr_rank_guardrail_failed player=Ryan Williams projection_rank=%s expected_max=10",
            ryan_projection_rank,
        )
    logger.info(
        "sheet_sync_wr_rank_guardrail_snapshot cam_projection_rank=%s cam_adp_rank=%s ryan_projection_rank=%s ryan_adp_rank=%s top10_wr=%s",
        cam_projection_rank,
        cam_adp_rank,
        ryan_projection_rank,
        ryan_adp_rank,
        [str(row.get("name") or "") for row in wr_rows[:10]],
    )

    if not valid_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no valid player rows found in sheet",
        )

    import_payload = DraftPlayerImportRequest(
        replace_mode=payload.replace_mode,
        rows=valid_rows,
    )
    imported_player_ids: set[int] = set()
    unmatched_names: list[str] = []
    matched_existing_counter = [0]
    imported = _import_draft_player_pool(
        db,
        payload=import_payload,
        collected_player_ids=imported_player_ids,
        unmatched_player_names=unmatched_names,
        matched_existing_counter=matched_existing_counter,
    )

    synced_at = datetime.now(timezone.utc)
    if imported_player_ids:
        players = db.query(Player).filter(Player.id.in_(imported_player_ids)).all()
        for player in players:
            player.sheet_source_sheet_id = sheet_id
            player.sheet_synced_at = synced_at
            db.add(player)

    watchlist = _get_or_create_global_watchlist(
        db,
        current_user=current_user,
        watchlist_name=payload.watchlist_name,
    )
    offensive_player_ids = {
        player_id
        for (player_id,) in db.query(Player.id)
        .filter(Player.id.in_(imported_player_ids), Player.position.in_(tuple(OFFENSE_DRAFT_POSITIONS)))
        .all()
    }
    watchlist_player_count = _replace_watchlist_players(
        db,
        watchlist_id=watchlist.id,
        player_ids=offensive_player_ids,
    )

    logger.info(
        "sheet_sync_summary sheet_id=%s received=%s valid=%s matched=%s unmatched=%s",
        sheet_id,
        total_received_rows,
        len(valid_rows),
        matched_existing_counter[0],
        len(unmatched_names),
    )
    if unmatched_names:
        logger.warning("sheet_sync_unmatched_players count=%s names=%s", len(unmatched_names), unmatched_names)

    sample_imported_rows = [
        {
            "player": str(row.get("name") or ""),
            "fantasy_proj": float(row.get("projected_fantasy_points") or 0),
        }
        for row in valid_rows[:25]
    ]
    logger.info("sheet_sync_sample_rows count=%s rows=%s", len(sample_imported_rows), sample_imported_rows)

    db.commit()
    return DraftSheetSyncResponse(
        received=total_received_rows,
        valid_rows=len(valid_rows),
        imported=imported,
        watchlist_id=watchlist.id,
        watchlist_name=watchlist.name,
        watchlist_player_count=watchlist_player_count,
        invalid_rows=invalid_rows[:200],
        sheet_id=sheet_id,
        matched_players=matched_existing_counter[0],
        unmatched_players=len(unmatched_names),
        unmatched_player_names=unmatched_names[:500],
        sample_imported_rows=sample_imported_rows,
    )


def _find_open_matchmaking_league(
    db: Session,
    *,
    team_count: int,
    skill_mode: str,
    current_user: User,
) -> League | None:
    scoring_key = f"matchmaking_{skill_mode}"
    candidates = (
        db.query(League)
        .filter(
            League.platform == "matchmaking",
            League.max_teams == team_count,
            League.scoring_type == scoring_key,
            League.status.in_(("matchmaking", "draft_scheduled")),
        )
        .order_by(League.created_at.asc(), League.id.asc())
        .all()
    )
    for league in candidates:
        already_member = (
            db.query(LeagueMember)
            .filter(
                LeagueMember.league_id == league.id,
                LeagueMember.user_id == current_user.id,
            )
            .first()
        )
        if already_member:
            return league
        member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
        if member_count < league.max_teams:
            return league
    return None


def _create_matchmaking_league(
    db: Session,
    *,
    team_count: int,
    skill_mode: str,
    current_user: User,
) -> League:
    now_utc = datetime.now(timezone.utc)
    league = League(
        name=f"Random {team_count} Team {skill_mode.title()} League",
        platform="matchmaking",
        scoring_type=f"matchmaking_{skill_mode}",
        commissioner_user_id=current_user.id,
        season_year=now_utc.year,
        max_teams=team_count,
        is_private=False,
        invite_code=None,
        description=f"Auto-match league for {skill_mode} skill mode",
        icon_url=None,
        status="matchmaking",
    )
    db.add(league)
    db.flush()

    scoring_json = {
        "ppr": 1,
        "pass_td": 4,
        "rush_td": 6,
        "rec_td": 6,
        "__meta__": {
            "skill_mode": skill_mode,
            "draft_order_strategy": "random",
            "matchmaking": True,
        },
    }

    db.add(
        LeagueSettings(
            league_id=league.id,
            scoring_json=scoring_json,
            roster_slots_json=FIXED_ROSTER_SLOTS,
            playoff_teams=4,
            waiver_type="faab",
            trade_review_type="commissioner",
            superflex_enabled=False,
            kicker_enabled=True,
            defense_enabled=False,
        )
    )
    db.add(
        Draft(
            league_id=league.id,
            draft_datetime_utc=now_utc + timedelta(days=7),
            timezone="UTC",
            draft_type="snake",
            pick_timer_seconds=90,
            status="scheduled",
        )
    )
    db.add(
        LeagueMember(
            league_id=league.id,
            user_id=current_user.id,
            role="commissioner",
        )
    )
    db.add(
        Team(
            league_id=league.id,
            name=f"{current_user.first_name}'s Team",
            owner_name=current_user.first_name,
            owner_user_id=current_user.id,
        )
    )
    db.flush()
    return league


def _ensure_public_waiting_joinable(league: League) -> None:
    if league.platform == "matchmaking":
        return
    if league.is_private:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="private leagues require an invite code",
        )
    if league.status not in PUBLIC_JOINABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league is not accepting joins right now",
        )


def _finalize_join_state(db: Session, league: League) -> None:
    _ensure_draft_order_when_full(db, league)
    if league.platform == "matchmaking":
        db.refresh(league)
        _update_matchmaking_draft_window_if_full(db, league)


@router.post("", response_model=LeagueCreateResponse, status_code=status.HTTP_201_CREATED)
def create_league_endpoint(
    payload: LeagueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    return create_league(payload, db, current_user)


@router.post("/create", response_model=LeagueCreateResponse, status_code=status.HTTP_201_CREATED)
def create_league_flow(
    payload: LeagueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    return create_league(payload, db, current_user)


@router.get("", response_model=LeagueList)
def list_leagues_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    scope: str = "member",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueList:
    leagues, total = list_leagues(
        db,
        limit=limit,
        offset=offset,
        user_id=current_user.id,
        scope=scope,
    )
    return LeagueList(
        data=[get_league_detail(db, league) for league in leagues],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/matchmaking/join", response_model=LeagueDetailRead)
def join_matchmaking(
    payload: MatchmakingJoinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    if payload.team_count not in MATCHMAKING_TEAM_COUNTS:
        allowed = ", ".join(str(value) for value in sorted(MATCHMAKING_TEAM_COUNTS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"team_count must be one of: {allowed}",
        )

    league = _find_open_matchmaking_league(
        db,
        team_count=payload.team_count,
        skill_mode=payload.skill_mode,
        current_user=current_user,
    )
    if not league:
        league = _create_matchmaking_league(
            db,
            team_count=payload.team_count,
            skill_mode=payload.skill_mode,
            current_user=current_user,
        )

    join_league_flow(db, league, current_user)
    db.refresh(league)
    _update_matchmaking_draft_window_if_full(db, league)
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


@router.get("/{league_id}", response_model=LeagueDetailRead)
def get_league_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league_id, current_user)
    return get_league_detail(db, league)


@router.get("/{league_id}/workspace", response_model=LeagueWorkspaceRead)
def get_league_workspace_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWorkspaceRead:
    league = get_league_or_404(db, league_id)
    membership = require_league_member(db, league.id, current_user)
    return build_league_workspace(db, league, membership, current_user)


@router.get("/{league_id}/matchups", response_model=LeagueScoreboardList)
def get_league_matchups_endpoint(
    league_id: int,
    week: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueScoreboardList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    rows = build_scoreboard_rows(db, league, week=week)
    return LeagueScoreboardList(data=rows, total=len(rows))


@router.get("/{league_id}/power-rankings", response_model=LeaguePowerRankingList)
def get_league_power_rankings_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeaguePowerRankingList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    rows = build_power_rankings_rows(db, league)
    return LeaguePowerRankingList(data=rows, total=len(rows))


@router.get("/{league_id}/news", response_model=LeagueNewsList)
def get_league_news_endpoint(
    league_id: int,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueNewsList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    rows = build_league_news_items(db, league, limit=limit)
    return LeagueNewsList(data=rows, total=len(rows), limit=limit)


@router.get("/{league_id}/weeks/{season}/{week}", response_model=LeagueWeekStateRead)
def get_league_week_state_endpoint(
    league_id: int,
    season: int,
    week: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWeekStateRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    state_row = get_or_create_week_state(db, league_id=league.id, season=season, week=week)
    db.commit()
    db.refresh(state_row)
    return LeagueWeekStateRead(
        league_id=state_row.league_id,
        season=state_row.season,
        week=state_row.week,
        status=state_row.status,
        locked_at=state_row.locked_at,
        finalized_at=state_row.finalized_at,
        corrected_at=state_row.corrected_at,
        updated_at=state_row.updated_at,
    )


@router.post("/{league_id}/weeks/{season}/{week}/status", response_model=LeagueWeekStateRead)
def update_league_week_state_endpoint(
    league_id: int,
    season: int,
    week: int,
    payload: LeagueWeekStateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWeekStateRead:
    league, _membership = require_commissioner(db, league_id, current_user)
    state_row = (
        db.query(LeagueWeekState)
        .filter(
            LeagueWeekState.league_id == league.id,
            LeagueWeekState.season == season,
            LeagueWeekState.week == week,
        )
        .with_for_update()
        .first()
    )
    if not state_row:
        state_row = get_or_create_week_state(db, league_id=league.id, season=season, week=week)
    transition_week_state(state_row=state_row, next_status=payload.status)
    db.add(state_row)
    append_admin_action(
        db,
        league_id=league.id,
        actor_user_id=current_user.id,
        action_type="league.week.status.changed",
        target_type="league_week",
        target_id=state_row.id,
        metadata={
            "season": season,
            "week": week,
            "status": state_row.status,
        },
    )
    db.commit()
    db.refresh(state_row)
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="league.week.status.changed",
        entity_type="league_week",
        entity_id=state_row.id,
        payload={
            "season": state_row.season,
            "week": state_row.week,
            "status": state_row.status,
        },
    )
    db.commit()
    return LeagueWeekStateRead(
        league_id=state_row.league_id,
        season=state_row.season,
        week=state_row.week,
        status=state_row.status,
        locked_at=state_row.locked_at,
        finalized_at=state_row.finalized_at,
        corrected_at=state_row.corrected_at,
        updated_at=state_row.updated_at,
    )


@router.post("/{league_id}/weeks/{season}/{week}/finalize", response_model=LeagueWeekFinalizeResponse)
def finalize_league_week_endpoint(
    league_id: int,
    season: int,
    week: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWeekFinalizeResponse:
    league, _membership = require_commissioner(db, league_id, current_user)

    week_matchups = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == season,
            Matchup.week == week,
        )
        .all()
    )
    if not week_matchups:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"no matchups found for season {season} week {week}",
        )
    pending = [row.id for row in week_matchups if row.status != "final"]
    if pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"cannot finalize week {week}; {len(pending)} matchup(s) are not final",
        )

    state_row = (
        db.query(LeagueWeekState)
        .filter(
            LeagueWeekState.league_id == league.id,
            LeagueWeekState.season == season,
            LeagueWeekState.week == week,
        )
        .with_for_update()
        .first()
    )
    if not state_row:
        state_row = get_or_create_week_state(db, league_id=league.id, season=season, week=week)

    if state_row.status == "open":
        transition_week_state(state_row=state_row, next_status="locked")
    if state_row.status == "locked":
        transition_week_state(state_row=state_row, next_status="finalized")
    elif state_row.status not in {"finalized", "corrected"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"cannot finalize week from state {state_row.status}",
        )

    standings_rows = build_standings_snapshot(
        db,
        league_id=league.id,
        season=season,
        through_week=week,
    )
    db.add(state_row)
    append_admin_action(
        db,
        league_id=league.id,
        actor_user_id=current_user.id,
        action_type="league.week.finalized",
        target_type="league_week",
        target_id=state_row.id,
        metadata={
            "season": season,
            "week": week,
            "status": state_row.status,
            "standings_count": len(standings_rows),
        },
    )
    db.commit()
    db.refresh(state_row)

    event_type = "league.week.corrected" if state_row.status == "corrected" else "league.week.finalized"
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type=event_type,
        entity_type="league_week",
        entity_id=state_row.id,
        payload={
            "season": season,
            "week": week,
            "status": state_row.status,
            "standings_count": len(standings_rows),
        },
    )
    db.commit()

    return LeagueWeekFinalizeResponse(
        league_id=league.id,
        season=season,
        week=week,
        status="corrected" if state_row.status == "corrected" else "finalized",
        finalized_at=state_row.finalized_at,
        standings=[
            LeagueWeekFinalizeStandingRead(
                team_id=row.team_id,
                wins=row.wins,
                losses=row.losses,
                ties=row.ties,
                points_for=float(row.points_for or 0.0),
                points_against=float(row.points_against or 0.0),
            )
            for row in standings_rows
        ],
    )


@router.post("/{league_id}/weeks/{season}/{week}/scores/recompute", response_model=LeagueWeekScoringRunResponse)
def recompute_league_week_scores_endpoint(
    league_id: int,
    season: int,
    week: int,
    payload: LeagueWeekScoringRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWeekScoringRunResponse:
    league, _membership = require_commissioner(db, league_id, current_user)
    execution = execute_week_scoring_run(
        db,
        league_id=league.id,
        season=season,
        week=week,
        source_mode=payload.source_mode,
        finalize_matchups=payload.finalize_matchups,
        finalize_week=payload.finalize_week,
        note=payload.note,
        created_by_user_id=current_user.id,
    )
    append_admin_action(
        db,
        league_id=league.id,
        actor_user_id=current_user.id,
        action_type="league.week.scoring.recomputed",
        target_type="scoring_run",
        target_id=execution.run_row.id,
        metadata={
            "season": season,
            "week": week,
            "source_mode": payload.source_mode,
            "finalize_matchups": payload.finalize_matchups,
            "finalize_week": payload.finalize_week,
            "week_state": execution.week_state.status,
            "player_actual_points_used": execution.scoring_result.player_actual_points_used,
            "player_projection_points_used": execution.scoring_result.player_projection_points_used,
            "standings_count": execution.standings_count,
        },
    )
    db.commit()
    db.refresh(execution.run_row)
    db.refresh(execution.week_state)

    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="league.week.scoring.recomputed",
        entity_type="scoring_run",
        entity_id=execution.run_row.id,
        payload={
            "season": season,
            "week": week,
            "source_mode": payload.source_mode,
            "finalize_matchups": payload.finalize_matchups,
            "finalize_week": payload.finalize_week,
            "week_state": execution.week_state.status,
            "player_actual_points_used": execution.scoring_result.player_actual_points_used,
            "player_projection_points_used": execution.scoring_result.player_projection_points_used,
            "standings_count": execution.standings_count,
        },
    )
    db.commit()

    return LeagueWeekScoringRunResponse(
        scoring_run_id=execution.run_row.id,
        league_id=league.id,
        season=season,
        week=week,
        source_mode=payload.source_mode,
        finalize_matchups=payload.finalize_matchups,
        finalize_week=payload.finalize_week,
        week_state=execution.week_state.status,
        standings_count=execution.standings_count,
        player_actual_points_used=execution.scoring_result.player_actual_points_used,
        player_projection_points_used=execution.scoring_result.player_projection_points_used,
        team_scores=[
            LeagueWeekScoreRowRead(
                team_id=row.team_id,
                team_name=row.team_name,
                starters_points=row.starters_points,
                bench_points=row.bench_points,
                total_points=row.total_points,
            )
            for row in execution.scoring_result.team_scores
        ],
        matchup_scores=[
            LeagueWeekMatchupScoreRead(
                matchup_id=row.matchup_id,
                home_team_id=row.home_team_id,
                away_team_id=row.away_team_id,
                home_score=row.home_score,
                away_score=row.away_score,
                status=row.status,
            )
            for row in execution.scoring_result.matchup_scores
        ],
    )


@router.get("/{league_id}/weeks/{season}/{week}/scores/runs", response_model=LeagueWeekScoringRunHistoryResponse)
def list_league_week_scoring_runs_endpoint(
    league_id: int,
    season: int,
    week: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWeekScoringRunHistoryResponse:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)

    rows = (
        db.query(ScoringRun)
        .filter(
            ScoringRun.league_id == league.id,
            ScoringRun.season == season,
            ScoringRun.week == week,
        )
        .order_by(ScoringRun.started_at.desc(), ScoringRun.id.desc())
        .all()
    )

    return LeagueWeekScoringRunHistoryResponse(
        league_id=league.id,
        season=season,
        week=week,
        data=[
            LeagueWeekScoringRunHistoryRow(
                scoring_run_id=row.id,
                source_mode=row.source_mode,
                status=row.status,
                finalize_matchups=bool(row.finalize_matchups),
                finalized_week_state=bool(row.finalized_week_state),
                started_at=row.started_at,
                completed_at=row.completed_at,
                created_by_user_id=row.created_by_user_id,
                note=row.note,
            )
            for row in rows
        ],
    )


@router.get("/{league_id}/draft-room", response_model=DraftRoomRead)
def get_draft_room_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    return draft_service.get_draft_room_state(db, league, current_user)


@router.get("/{league_id}/draft-room/snapshot", response_model=DraftRoomSnapshotRead)
def get_draft_room_snapshot_endpoint(
    league_id: int,
    since_seq: int = Query(0, ge=0),
    limit: int = Query(250, ge=1, le=250),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomSnapshotRead:
    league = get_league_or_404(db, league_id)
    room = draft_service.get_draft_room_state(db, league, current_user)
    events = list_league_events_since(
        db,
        league_id=league.id,
        since_seq=max(0, since_seq),
        limit=limit,
    )
    envelopes = [_event_row_to_envelope(event_row) for event_row in events]
    latest_seq = latest_league_event_seq(db, league_id=league.id)
    return DraftRoomSnapshotRead(
        draft_room=room,
        events=envelopes,
        latest_seq=latest_seq,
    )


@router.get("/{league_id}/events", response_model=LeagueEventListRead)
def list_league_events_endpoint(
    league_id: int,
    since_seq: int = Query(0, ge=0),
    limit: int = Query(250, ge=1, le=250),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueEventListRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)

    rows = list_league_events_since(
        db,
        league_id=league.id,
        since_seq=max(0, since_seq),
        limit=limit,
    )
    latest_seq = latest_league_event_seq(db, league_id=league.id)
    return LeagueEventListRead(
        data=[_event_row_to_envelope(row) for row in rows],
        latest_seq=latest_seq,
    )


@router.get("/{league_id}/audit-log", response_model=AdminActionListRead)
def list_league_audit_log_endpoint(
    league_id: int,
    since_id: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminActionListRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    rows, total = list_admin_actions(
        db,
        league_id=league.id,
        since_id=max(0, since_id),
        limit=limit,
        offset=offset,
    )
    resolved_limit = max(1, min(limit, 200))
    resolved_offset = max(0, offset)
    return AdminActionListRead(
        data=[
            AdminActionRead(
                id=row.id,
                league_id=row.league_id,
                actor_user_id=row.actor_user_id,
                action_type=row.action_type,
                target_type=row.target_type,
                target_id=row.target_id,
                metadata=row.meta or {},
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
        limit=resolved_limit,
        offset=resolved_offset,
    )


@router.websocket("/{league_id}/draft-room/ws")
async def draft_room_ws_endpoint(websocket: WebSocket, league_id: int) -> None:
    token = websocket.query_params.get("token")
    with SessionLocal() as db:
        try:
            current_user = _get_user_from_ws_token(db, token)
            league = get_league_or_404(db, league_id)
            require_league_member(db, league.id, current_user)
            initial_room = _draft_room_state(db, league, current_user)
        except HTTPException as exc:
            close_code = 4401 if exc.status_code == status.HTTP_401_UNAUTHORIZED else 4403
            await websocket.close(code=close_code)
            return

    await draft_realtime_manager.connect(league_id, websocket)
    try:
        await websocket.send_json(
            {
                "event": "draft_room_ready",
                "event_id": f"snapshot_{league_id}_{initial_room.server_state_seq}",
                "event_type": "draft.room.snapshot",
                "entity_type": "draft_room",
                "entity_id": initial_room.draft_room_id,
                "seq": initial_room.server_state_seq,
                "schema_version": EVENT_SCHEMA_VERSION,
                "league_id": league_id,
                "at": datetime.now(timezone.utc).isoformat(),
                "payload": {"draft_room": initial_room.model_dump(mode="json")},
            }
        )
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"event": "pong", "league_id": league_id, "payload": {}})
    except WebSocketDisconnect:
        await draft_realtime_manager.disconnect(league_id, websocket)
    except Exception:
        await draft_realtime_manager.disconnect(league_id, websocket)


@router.post("/{league_id}/draft-room/practice-setup", response_model=DraftRoomRead)
def practice_setup_draft_room_endpoint(
    league_id: int,
    payload: DraftPracticeSetupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league, _membership = require_commissioner(db, league_id, current_user)
    _setup_draft_practice(db, league=league, payload=payload, current_user=current_user)
    append_admin_action(
        db,
        league_id=league_id,
        actor_user_id=current_user.id,
        action_type="draft.practice_setup",
        target_type="draft_room",
        metadata={
            "team_count": payload.team_count,
            "reset_existing": payload.reset_existing,
            "start_now": payload.start_now,
            "mock_team_prefix": payload.mock_team_prefix,
        },
    )
    _emit_draft_event(
        db,
        league_id=league_id,
        event_type="draft.room.updated",
        entity_type="draft_room",
        payload={"reason": "practice_setup"},
    )
    db.commit()
    room = _draft_room_state(db, league, current_user)
    return room


@router.post("/{league_id}/draft-room/status", response_model=DraftRoomRead)
def update_draft_room_status_endpoint(
    league_id: int,
    payload: DraftRoomStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league, _membership = require_commissioner(db, league_id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    if draft_row.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")
    timer_state = _get_or_create_draft_timer_state(db, draft_row.id)
    now_utc = datetime.now(timezone.utc)

    def _require_empty_draft_for_countdown() -> None:
        existing_pick_count = db.query(DraftPick.id).filter(DraftPick.draft_id == draft_row.id).count()
        if existing_pick_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot start countdown with existing picks. Run practice setup reset first.",
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
            _require_empty_draft_for_countdown()
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
            _require_empty_draft_for_countdown()
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
    db.commit()
    _emit_draft_event(
        db,
        league_id=league_id,
        event_type="draft.status.changed",
        entity_type="draft_room",
        entity_id=draft_row.id,
        payload={"status": draft_row.status},
    )
    db.commit()
    room = _draft_room_state(db, league, current_user)
    return room


@router.post("/{league_id}/draft-room/lobby/join", response_model=DraftRoomRead)
def join_draft_lobby_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    teams = _ordered_draft_teams(db, league.id)
    team = _resolve_user_draft_team(
        db,
        teams=teams,
        league=league,
        current_user=current_user,
        draft_status=draft_row.status,
    )
    row = _upsert_lobby_member(
        db,
        draft_id=draft_row.id,
        team_id=team.id,
        user_id=current_user.id,
        set_ready=None,
    )
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.lobby.updated",
        entity_type="draft_room",
        entity_id=draft_row.id,
        payload={
            "action": "join",
            "team_id": team.id,
            "user_id": current_user.id,
            "ready": bool(row.is_ready),
        },
    )
    db.commit()
    return _draft_room_state(db, league, current_user)


@router.post("/{league_id}/draft-room/lobby/ready", response_model=DraftRoomRead)
def set_draft_lobby_ready_endpoint(
    league_id: int,
    payload: DraftLobbyReadyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    teams = _ordered_draft_teams(db, league.id)
    team = _resolve_user_draft_team(
        db,
        teams=teams,
        league=league,
        current_user=current_user,
        draft_status=draft_row.status,
    )
    row = _upsert_lobby_member(
        db,
        draft_id=draft_row.id,
        team_id=team.id,
        user_id=current_user.id,
        set_ready=payload.ready,
    )
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.lobby.updated",
        entity_type="draft_room",
        entity_id=draft_row.id,
        payload={
            "action": "ready",
            "team_id": team.id,
            "user_id": current_user.id,
            "ready": bool(row.is_ready),
        },
    )
    db.commit()
    return _draft_room_state(db, league, current_user)


@router.post("/{league_id}/draft-room/lobby/heartbeat", response_model=DraftRoomRead)
def heartbeat_draft_lobby_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    teams = _ordered_draft_teams(db, league.id)
    team = _resolve_user_draft_team(
        db,
        teams=teams,
        league=league,
        current_user=current_user,
        draft_status=draft_row.status,
    )
    _upsert_lobby_member(
        db,
        draft_id=draft_row.id,
        team_id=team.id,
        user_id=current_user.id,
        set_ready=None,
    )
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.lobby.updated",
        entity_type="draft_room",
        entity_id=draft_row.id,
        payload={
            "action": "heartbeat",
            "team_id": team.id,
            "user_id": current_user.id,
        },
    )
    db.commit()
    return _draft_room_state(db, league, current_user)


@router.post("/{league_id}/draft-room/slots/move", response_model=DraftRoomRead)
def move_draft_slot_endpoint(
    league_id: int,
    payload: DraftSlotMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league, _membership = require_commissioner(db, league_id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    if draft_row.status in {"live", "paused", "completed", "abandoned"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot move draft slots after the draft is live.",
        )

    teams = _ordered_draft_teams(db, league.id)
    if not teams:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no teams available for draft")

    order_ids = [team.id for team in teams]
    max_slot = len(order_ids)
    from_slot = int(payload.from_slot)
    to_slot = int(payload.to_slot)
    if from_slot > max_slot or to_slot > max_slot:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"slot must be between 1 and {max_slot}",
        )
    if from_slot == to_slot:
        return _draft_room_state(db, league, current_user)

    moved_team_id = order_ids.pop(from_slot - 1)
    order_ids.insert(to_slot - 1, moved_team_id)
    _persist_draft_order(
        db,
        league_id=league.id,
        ordered_team_ids=order_ids,
        strategy=_draft_order_strategy_for_league(db, league.id),
    )

    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.lobby.updated",
        entity_type="draft_room",
        entity_id=draft_row.id,
        payload={
            "action": "slot_move",
            "from_slot": from_slot,
            "to_slot": to_slot,
            "team_id": moved_team_id,
            "moved_by_user_id": current_user.id,
        },
    )
    db.commit()
    return _draft_room_state(db, league, current_user)


@router.post(
    "/{league_id}/draft-room/player-pool/import",
    response_model=DraftPlayerImportResponse,
)
def import_draft_player_pool_endpoint(
    league_id: int,
    payload: DraftPlayerImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftPlayerImportResponse:
    _league, _membership = require_commissioner(db, league_id, current_user)
    return _import_draft_player_pool(db, payload=payload)


@router.post(
    "/{league_id}/draft-room/sheet-sync",
    response_model=DraftSheetSyncResponse,
)
def sheet_sync_draft_room_endpoint(
    league_id: int,
    payload: DraftSheetSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftSheetSyncResponse:
    league, _membership = require_commissioner(db, league_id, current_user)
    result = _sync_sheet_to_draft_and_watchlist(
        db,
        payload=payload,
        current_user=current_user,
        season_year=league.season_year,
    )
    _emit_draft_event(
        db,
        league_id=league_id,
        event_type="draft.player_pool.updated",
        entity_type="league",
        entity_id=league_id,
        payload={
            "valid_rows": result.valid_rows,
            "matched_players": result.matched_players,
            "unmatched_players": result.unmatched_players,
        },
    )
    db.commit()
    return result


def _resolve_queue_team_for_user(
    db: Session,
    *,
    league: League,
    current_user: User,
    requested_team_id: int | None = None,
) -> Team:
    membership = require_league_member(db, league.id, current_user)
    teams = _ordered_draft_teams(db, league.id)
    if not teams:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no teams available for draft")

    if requested_team_id is not None:
        selected = next((team for team in teams if team.id == requested_team_id), None)
        if selected is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team not found in this league")
        is_commissioner = membership.role == "commissioner" or league.commissioner_user_id == current_user.id
        if not is_commissioner and selected.owner_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team queue access denied")
        return selected

    owned = next((team for team in teams if team.owner_user_id == current_user.id), None)
    if owned:
        return owned

    if membership.role == "commissioner" or league.commissioner_user_id == current_user.id:
        return teams[0]

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="no owned team found for this user in draft room",
    )


@router.get("/{league_id}/draft-room/queue", response_model=DraftQueueRead)
def get_draft_queue_endpoint(
    league_id: int,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftQueueRead:
    league = get_league_or_404(db, league_id)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    team = _resolve_queue_team_for_user(
        db,
        league=league,
        current_user=current_user,
        requested_team_id=team_id,
    )
    queue = _draft_queue_state(
        db,
        league=league,
        draft_row=draft_row,
        team_id=team.id,
    )
    db.commit()
    return queue


@router.post("/{league_id}/draft-room/queue", response_model=DraftQueueRead)
def add_to_draft_queue_endpoint(
    league_id: int,
    payload: DraftQueueAddRequest,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftQueueRead:
    league = get_league_or_404(db, league_id)
    draft_row = (
        db.query(Draft)
        .filter(Draft.league_id == league.id)
        .with_for_update()
        .first()
    )
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    team = _resolve_queue_team_for_user(
        db,
        league=league,
        current_user=current_user,
        requested_team_id=team_id,
    )
    player = db.query(Player).filter(Player.id == payload.player_id).first()
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    existing_pick = (
        db.query(DraftPick.id)
        .filter(DraftPick.draft_id == draft_row.id, DraftPick.player_id == player.id)
        .first()
    )
    existing_roster = (
        db.query(RosterEntry.id)
        .filter(RosterEntry.league_id == league.id, RosterEntry.player_id == player.id)
        .first()
    )
    if existing_pick or existing_roster:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already drafted")

    existing_queue = (
        db.query(DraftTeamQueueItem)
        .filter(
            DraftTeamQueueItem.draft_id == draft_row.id,
            DraftTeamQueueItem.team_id == team.id,
            DraftTeamQueueItem.player_id == player.id,
        )
        .first()
    )
    if not existing_queue:
        next_priority = (
            db.query(func.max(DraftTeamQueueItem.priority))
            .filter(
                DraftTeamQueueItem.draft_id == draft_row.id,
                DraftTeamQueueItem.team_id == team.id,
            )
            .scalar()
            or 0
        )
        db.add(
            DraftTeamQueueItem(
                draft_id=draft_row.id,
                team_id=team.id,
                player_id=player.id,
                priority=int(next_priority) + 1,
            )
        )
        db.flush()

    queue = _draft_queue_state(db, league=league, draft_row=draft_row, team_id=team.id)
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.queue.updated",
        entity_type="team",
        entity_id=team.id,
        payload={"team_id": team.id, "count": queue.count},
    )
    db.commit()
    return queue


@router.post("/{league_id}/draft-room/queue/reorder", response_model=DraftQueueRead)
def reorder_draft_queue_endpoint(
    league_id: int,
    payload: DraftQueueReorderRequest,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftQueueRead:
    league = get_league_or_404(db, league_id)
    draft_row = (
        db.query(Draft)
        .filter(Draft.league_id == league.id)
        .with_for_update()
        .first()
    )
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    team = _resolve_queue_team_for_user(
        db,
        league=league,
        current_user=current_user,
        requested_team_id=team_id,
    )
    queue_rows = _normalize_queue_priorities(db, draft_id=draft_row.id, team_id=team.id)
    row_by_player = {int(row.player_id): row for row in queue_rows}

    unique_ids: list[int] = []
    seen = set()
    for value in payload.player_ids:
        if value in seen:
            continue
        seen.add(value)
        if value in row_by_player:
            unique_ids.append(value)

    remaining_ids = [int(row.player_id) for row in queue_rows if int(row.player_id) not in seen]
    ordered_ids = [*unique_ids, *remaining_ids]
    for index, player_id in enumerate(ordered_ids, start=1):
        row = row_by_player[player_id]
        row.priority = index
        db.add(row)
    db.flush()

    queue = _draft_queue_state(db, league=league, draft_row=draft_row, team_id=team.id)
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.queue.updated",
        entity_type="team",
        entity_id=team.id,
        payload={"team_id": team.id, "count": queue.count},
    )
    db.commit()
    return queue


@router.delete("/{league_id}/draft-room/queue/{player_id}", response_model=DraftQueueRead)
def remove_from_draft_queue_endpoint(
    league_id: int,
    player_id: int,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftQueueRead:
    league = get_league_or_404(db, league_id)
    draft_row = (
        db.query(Draft)
        .filter(Draft.league_id == league.id)
        .with_for_update()
        .first()
    )
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    team = _resolve_queue_team_for_user(
        db,
        league=league,
        current_user=current_user,
        requested_team_id=team_id,
    )
    (
        db.query(DraftTeamQueueItem)
        .filter(
            DraftTeamQueueItem.draft_id == draft_row.id,
            DraftTeamQueueItem.team_id == team.id,
            DraftTeamQueueItem.player_id == player_id,
        )
        .delete(synchronize_session=False)
    )
    db.flush()
    queue = _draft_queue_state(db, league=league, draft_row=draft_row, team_id=team.id)
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.queue.updated",
        entity_type="team",
        entity_id=team.id,
        payload={"team_id": team.id, "count": queue.count},
    )
    db.commit()
    return queue


@router.post("/{league_id}/draft-room/queue/clear", response_model=DraftQueueRead)
def clear_draft_queue_endpoint(
    league_id: int,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftQueueRead:
    league = get_league_or_404(db, league_id)
    draft_row = (
        db.query(Draft)
        .filter(Draft.league_id == league.id)
        .with_for_update()
        .first()
    )
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    team = _resolve_queue_team_for_user(
        db,
        league=league,
        current_user=current_user,
        requested_team_id=team_id,
    )
    (
        db.query(DraftTeamQueueItem)
        .filter(
            DraftTeamQueueItem.draft_id == draft_row.id,
            DraftTeamQueueItem.team_id == team.id,
        )
        .delete(synchronize_session=False)
    )
    db.flush()
    queue = _draft_queue_state(db, league=league, draft_row=draft_row, team_id=team.id)
    _emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.queue.updated",
        entity_type="team",
        entity_id=team.id,
        payload={"team_id": team.id, "count": queue.count},
    )
    db.commit()
    return queue


@router.post("/{league_id}/draft-picks", response_model=DraftRoomRead, status_code=status.HTTP_201_CREATED)
def create_draft_pick_endpoint(
    league_id: int,
    payload: DraftPickCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    return draft_service.create_real_draft_pick(
        db,
        league,
        payload,
        current_user,
        idempotency_key=idempotency_key,
    )


@router.post("/{league_id}/draft-picks/auto", response_model=DraftRoomRead)
def create_auto_draft_pick_endpoint(
    league_id: int,
    payload: DraftAutoPickRequest | None = None,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    force_pick = bool(force or (payload.force if payload else False))
    changed = _autopick_timed_out_current_team(
        db,
        league=league,
        current_user=current_user,
        force=force_pick,
    )
    if not changed:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft clock has not expired or no legal auto-pick is available.",
        )
    db.commit()
    return _draft_room_state(db, league, current_user)


@router.get("/{league_id}/draft-history", response_model=DraftHistoryResponse)
def get_draft_history_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftHistoryResponse:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    return generate_draft_history(db, league=league, draft_row=draft_row)


@router.post("/{league_id}/draft-history/email", response_model=DraftHistoryEmailResponse)
def email_draft_history_endpoint(
    league_id: int,
    payload: DraftHistoryEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftHistoryEmailResponse:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    if draft_row.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft is not complete")

    history = generate_draft_history(db, league=league, draft_row=draft_row)
    emails: list[str] = []
    if payload.send_to_account_email:
        account_email = _normalize_summary_email(current_user.email)
        if account_email:
            emails.append(account_email)
    additional_email = _normalize_summary_email(payload.additional_email)
    if additional_email and additional_email not in emails:
        emails.append(additional_email)
    if not emails:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="choose at least one email")
    if not settings.resend_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Email provider is not configured. Copy or download the draft history instead.",
                "history": history.model_dump(mode="json"),
            },
        )

    now_utc = datetime.now(timezone.utc)
    db.add(
        NotificationLog(
            user_id=current_user.id,
            user_key=str(current_user.id),
            alert_type="draft_summary",
            title=f"{league.name} Draft History",
            body=history.plain_text[:500],
            payload={"league_id": league.id, "draft_id": draft_row.id, "emails": emails},
            sent_at=now_utc,
        )
    )
    draft_row.history_email_sent_at = now_utc
    db.add(draft_row)
    db.commit()
    return DraftHistoryEmailResponse(sent=True, emails=emails, history=history)


@router.get("/{league_id}/members", response_model=LeagueMembersList)
def list_league_members(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueMembersList:
    require_league_member(db, league_id, current_user)
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league_id).all()
    return LeagueMembersList(data=[LeagueMemberRead.model_validate(m) for m in members], total=len(members))


@router.post("/join-by-code", response_model=LeaguePreview)
def join_by_code(payload: JoinByCodeRequest, db: Session = Depends(get_db)) -> LeaguePreview:
    invite = (
        db.query(LeagueInvite)
        .filter(LeagueInvite.code == payload.invite_code.upper(), LeagueInvite.active.is_(True))
        .first()
    )
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite code not found")
    league = db.get(League, invite.league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    commissioner = db.query(User).filter(User.id == league.commissioner_user_id).first()
    return LeaguePreview(
        id=league.id,
        name=league.name,
        commissioner_name=commissioner.first_name if commissioner else None,
        max_teams=league.max_teams,
        member_count=member_count,
        is_private=league.is_private,
        draft_datetime_utc=draft_row.draft_datetime_utc if draft_row else None,
        timezone=draft_row.timezone if draft_row else None,
        scoring_preset=league.scoring_type,
    )


@router.post("/join-with-code", response_model=LeagueDetailRead)
def join_with_code(
    payload: JoinByCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    invite = (
        db.query(LeagueInvite)
        .filter(LeagueInvite.code == payload.invite_code.upper(), LeagueInvite.active.is_(True))
        .first()
    )
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite code not found")
    league = db.get(League, invite.league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    if league.status not in PUBLIC_JOINABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league is not accepting joins right now",
        )
    join_league_flow(db, league, current_user)
    _finalize_join_state(db, league)
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


@router.post("/{league_id}/join", response_model=LeagueDetailRead)
def join_league(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    _ensure_public_waiting_joinable(league)
    join_league_flow(db, league, current_user)
    _finalize_join_state(db, league)
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


@router.post("/{league_id}/regenerate-invite", response_model=LeagueCreateResponse)
def regenerate_invite(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    league, _ = require_commissioner(db, league_id, current_user)
    return regenerate_invite_flow(db, league, current_user)


@router.patch("/{league_id}/settings", response_model=LeagueDetailRead)
def update_league_settings(
    league_id: int,
    payload: LeagueSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    league, _ = require_commissioner(db, league_id, current_user)
    return update_league_settings_flow(db, league, payload)


@router.patch("/{league_id}/draft", response_model=DraftRead)
def reschedule_draft(
    league_id: int,
    payload: DraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRead:
    league, _ = require_commissioner(db, league_id, current_user)
    return reschedule_draft_flow(db, league, payload)


@router.delete("/{league_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_league_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    league, _ = require_commissioner(db, league_id, current_user)
    delete_league(db, league)
