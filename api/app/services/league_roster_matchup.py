import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.core.config import settings as app_settings
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.live_player_projection import LivePlayerProjection
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_waiver_availability import PlayerWaiverAvailability
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.postseason import PostseasonMatchup
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_period import WaiverPeriod
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.domain.scoring_engine import (
    calculate_player_fantasy_points,
    normalize_player_stats,
)
from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.schemas.league_flow import (
    LeagueMatchupTabRead,
    LiveScoringFreshnessRead,
    PostseasonMatchupContextRead,
    LeagueInviteSettingsRead,
    LeagueMemberRead,
    LeagueRosterTabRead,
    LeagueRosterTeamRead,
    LeagueScheduleRowRead,
    LeagueSettingsViewRead,
    LeagueTradeHistoryAssetRead,
    LeagueTradeHistoryPartyRead,
    LeagueTradeHistoryRead,
    LeagueWorkspaceTeamRead,
    LeagueWaiverPlayerRead,
    LeagueWaiverPeriodRead,
    LeagueWaiversRead,
    MatchupTeamRead,
    RosterTabEntryRead,
    RosterTabTeamRead,
)
from collegefootballfantasy_api.app.schemas.waiver import WaiverDropCandidateRead
from collegefootballfantasy_api.app.services.league_weeks import resolve_current_week
from collegefootballfantasy_api.app.services.espn_live_scoring import espn_week_freshness
from collegefootballfantasy_api.app.services.injury_status import is_current_injury_designation, normalize_injury_status
from collegefootballfantasy_api.app.services.league_workspace import build_standings_summary
from collegefootballfantasy_api.app.services.matchup_probability import (
    calculate_matchup_win_probability,
)
from collegefootballfantasy_api.app.services.player_lock_service import as_utc, game_context_for_players
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school
from collegefootballfantasy_api.app.services.roster_slots import CanonicalRosterSlot, build_team_roster_slots
from collegefootballfantasy_api.app.services.waiver_service import (
    serialize_claims,
    waiver_player_availability_states,
    waiver_window_state,
)
from collegefootballfantasy_api.app.services.league_rivalry import matchup_rivalry_context

DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BENCH": 4,
    "IR": 1,
}

ESPN_PROVIDER = "espn"


@dataclass(frozen=True)
class LiveGameContext:
    state: str = "unavailable"
    has_possession: bool = False
    in_red_zone: bool = False
    game_period: int | None = None
    game_clock: str | None = None
    game_score: str | None = None
    game_down_distance: str | None = None
    game_is_halftime: bool = False


def _live_projection_map(
    db: Session, *, season: int, week: int, player_ids: set[int]
) -> dict[int, LivePlayerProjection]:
    if not player_ids:
        return {}
    rows = db.query(LivePlayerProjection).filter(
        LivePlayerProjection.season == season,
        LivePlayerProjection.week == week,
        LivePlayerProjection.player_id.in_(player_ids),
    ).order_by(LivePlayerProjection.provider_snapshot_at.desc(), LivePlayerProjection.id.desc()).all()
    result: dict[int, LivePlayerProjection] = {}
    for row in rows:
        result.setdefault(row.player_id, row)
    return result


def _school_key(value: str | None) -> str | None:
    if not value:
        return None
    return canonical_school_name(value) or normalize_school(value)


def _display_school_name(value: str | None) -> str | None:
    if not value:
        return value
    return canonical_school_name(value) or value


def _summary_live_context(payload: dict[str, Any]) -> tuple[LiveGameContext, set[str]]:
    """Read the live game context from the accepted cached ESPN summary only.

    The roster endpoint must never make a provider call. ESPN's summary payload
    identifies the offense by competitor id (or a competitor possession flag)
    and exposes ``situation`` game state while live. Missing fields stay null
    rather than being guessed from play text or score shape.
    """

    header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
    competitions = header.get("competitions") if isinstance(header.get("competitions"), list) else []
    competition = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    status = competition.get("status") if isinstance(competition.get("status"), dict) else {}
    status_type = status.get("type") if isinstance(status.get("type"), dict) else {}
    state = str(status_type.get("state") or "unavailable").strip().lower()
    state = "live" if state == "in" else "final" if state == "post" or status_type.get("completed") is True else "scheduled" if state == "pre" else "unavailable"
    if state != "live":
        return LiveGameContext(state=state), set()

    situation = payload.get("situation") if isinstance(payload.get("situation"), dict) else {}
    period_value = status.get("period")
    try:
        game_period = int(period_value) if period_value is not None else None
    except (TypeError, ValueError):
        game_period = None
    game_clock_value = status.get("displayClock") or status.get("clock")
    game_clock = str(game_clock_value).strip() if game_clock_value is not None else None
    if not game_clock:
        game_clock = None

    status_detail = " ".join(
        str(status_type.get(key) or "") for key in ("detail", "shortDetail", "description")
    ).lower()
    is_halftime = "halftime" in status_detail

    def _competitor_label(competitor: dict[str, Any]) -> str | None:
        team = competitor.get("team") if isinstance(competitor.get("team"), dict) else {}
        for value in (team.get("location"), team.get("shortDisplayName"), team.get("displayName"), team.get("abbreviation")):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _competitor_score(competitor: dict[str, Any]) -> str | None:
        value = competitor.get("score")
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
        return None

    possession_id = str(situation.get("possession") or "").strip()
    possession_keys: set[str] = set()
    competitors = competition.get("competitors") if isinstance(competition.get("competitors"), list) else []
    home_competitor: dict[str, Any] | None = None
    away_competitor: dict[str, Any] | None = None
    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        home_away = str(competitor.get("homeAway") or "").strip().lower()
        if home_away == "home":
            home_competitor = competitor
        elif home_away == "away":
            away_competitor = competitor
        team = competitor.get("team") if isinstance(competitor.get("team"), dict) else {}
        competitor_id = str(competitor.get("id") or team.get("id") or "").strip()
        is_possession = (
            possession_id == competitor_id
            if possession_id
            else bool(competitor.get("possession"))
        )
        if not is_possession:
            continue
        for name in (team.get("location"), team.get("shortDisplayName"), team.get("displayName")):
            if isinstance(name, str) and (key := _school_key(name)):
                possession_keys.add(key)

    score: str | None = None
    if home_competitor is not None and away_competitor is not None:
        home_label, home_score = _competitor_label(home_competitor), _competitor_score(home_competitor)
        away_label, away_score = _competitor_label(away_competitor), _competitor_score(away_competitor)
        if home_label and home_score is not None and away_label and away_score is not None:
            score = f"{away_label} {away_score} – {home_label} {home_score}"

    down_distance: str | None = None
    value = situation.get("downDistanceText")
    if isinstance(value, str) and value.strip():
        down_distance = value.strip()
    else:
        try:
            down = int(situation.get("down"))
            distance = int(situation.get("distance"))
        except (TypeError, ValueError):
            down = distance = None
        if down is not None and distance is not None and down > 0 and distance >= 0:
            suffix = "th" if 10 <= down % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(down % 10, "th")
            down_distance = f"{down}{suffix} & {distance}"

    return (
        LiveGameContext(
            state=state,
            in_red_zone=situation.get("isRedZone") is True,
            game_period=game_period,
            game_clock=game_clock,
            game_score=score,
            game_down_distance=down_distance,
            game_is_halftime=is_halftime,
        ),
        possession_keys,
    )


def _live_game_context_by_player(
    db: Session,
    *,
    season: int,
    week: int,
    player_schools: dict[int, str | None],
    games: list[Game] | None = None,
) -> dict[int, LiveGameContext]:
    """Map rostered schools to accepted ESPN game snapshots without I/O."""

    school_to_game_id: dict[str, str | None] = {}
    if games is None:
        games = db.query(Game).filter(Game.season == season, Game.week == week).all()
    for game in games:
        provider_game_id = str(game.external_id or "").strip() or None
        for school in (game.home_team, game.away_team):
            key = _school_key(school)
            if not key:
                continue
            if key in school_to_game_id and school_to_game_id[key] != provider_game_id:
                school_to_game_id[key] = None
            else:
                school_to_game_id[key] = provider_game_id
    game_ids = {game_id for game_id in school_to_game_id.values() if game_id}
    polls = {
        poll.provider_game_id: poll
        for poll in db.query(ProviderGamePoll)
        .filter(
            ProviderGamePoll.provider == ESPN_PROVIDER,
            ProviderGamePoll.season == season,
            ProviderGamePoll.week == week,
            ProviderGamePoll.provider_game_id.in_(game_ids),
        )
        .all()
    } if game_ids else {}
    contexts: dict[int, LiveGameContext] = {}
    parsed: dict[str, tuple[LiveGameContext, set[str]]] = {}
    for player_id, school in player_schools.items():
        key = _school_key(school)
        game_id = school_to_game_id.get(key) if key else None
        poll = polls.get(game_id) if game_id else None
        if poll is None or not poll.accepted_snapshot_hash or not isinstance(poll.latest_payload, dict):
            contexts[player_id] = LiveGameContext()
            continue
        if game_id not in parsed:
            parsed[game_id] = _summary_live_context(poll.latest_payload)
        game_context, possession_keys = parsed[game_id]
        has_possession = bool(key and key in possession_keys)
        contexts[player_id] = replace(
            game_context,
            has_possession=has_possession,
            in_red_zone=bool(game_context.in_red_zone and has_possession),
        )
    return contexts


def _slot_limits(db: Session, league: League) -> dict[str, int]:
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    slot_limits = DEFAULT_ROSTER_SLOTS.copy()
    if settings and settings.roster_slots_json:
        slot_limits.update(settings.roster_slots_json)
    return slot_limits


def _serialize_waiver_period(period: WaiverPeriod | None) -> LeagueWaiverPeriodRead | None:
    if period is None:
        return None
    return LeagueWaiverPeriodRead(
        id=period.id,
        season=period.season,
        week=period.week,
        window_key=period.window_key,
        opens_at=period.opens_at,
        closes_at=period.closes_at,
        processes_at=period.processes_at,
        status=period.status,
    )


def _owned_team(db: Session, league: League, user: User) -> Team | None:
    return (
        db.query(Team)
        .filter(Team.league_id == league.id, Team.owner_user_id == user.id)
        .first()
    )


def _team_record(db: Session, league: League, team_id: int) -> str:
    return _team_records(db, league, {team_id}).get(team_id, "0-0-0")


def _team_records(db: Session, league: League, team_ids: set[int]) -> dict[int, str]:
    if not team_ids:
        return {}
    standings = (
        db.query(Standing)
        .filter(
            Standing.league_id == league.id,
            Standing.season == league.season_year,
            Standing.team_id.in_(team_ids),
        )
        .order_by(Standing.team_id.asc(), Standing.week.desc(), Standing.id.desc())
        .all()
    )
    records = {team_id: "0-0-0" for team_id in team_ids}
    seen_team_ids: set[int] = set()
    for standing in standings:
        if standing.team_id not in seen_team_ids:
            records[standing.team_id] = f"{standing.wins}-{standing.losses}-{standing.ties}"
            seen_team_ids.add(standing.team_id)
    return records


def _owner_avatar_urls(db: Session, teams: list[Team], viewer: User) -> dict[int, str | None]:
    """Fetch visible matchup manager avatars in one bounded query when needed."""
    owner_ids = {team.owner_user_id for team in teams if team.owner_user_id is not None}
    if not owner_ids:
        return {}
    # The authenticated viewer was already loaded to authorize this request,
    # so reuse it when their team is on the matchup instead of querying their
    # avatar again. The remaining opponents are fetched as one batch.
    avatars = {viewer.id: viewer.avatar_url} if viewer.id in owner_ids else {}
    owner_ids -= set(avatars)
    if not owner_ids:
        return avatars
    avatars.update({
        user_id: avatar_url
        for user_id, avatar_url in db.query(User.id, User.avatar_url).filter(User.id.in_(owner_ids)).all()
    })
    return avatars


def _team_read(db: Session, league: League, team: Team) -> RosterTabTeamRead:
    return RosterTabTeamRead(
        id=team.id,
        name=team.display_name,
        owner_user_id=team.owner_user_id,
        record=_team_record(db, league, team.id),
    )


def _projection_map(
    db: Session,
    season: int,
    week: int,
    player_ids: set[int],
) -> dict[int, WeeklyProjection]:
    if not player_ids:
        return {}
    rows = db.scalars(
        current_published_projections_query(
            season=season,
            week=week,
            player_ids=player_ids,
        )
    ).all()
    return {row.player_id: row for row in rows}


def _player_week_score_map(
    db: Session,
    league_id: int,
    season: int,
    week: int,
    player_ids: set[int],
) -> dict[int, PlayerWeekScore]:
    if not player_ids:
        return {}
    rows = (
        db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
            PlayerWeekScore.player_id.in_(player_ids),
        )
        .all()
    )
    return {row.player_id: row for row in rows}


def _stat_value(stats: dict[str, Any], *keys: str) -> int | float:
    for key in keys:
        value = stats.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return int(value) if float(value).is_integer() else float(value)
    return 0


def _compact_game_stat_line(stats: dict[str, Any], position: str | None) -> str:
    """Return the roster row's compact current-game box-score shorthand.

    Live-provider snapshots and verified final box scores use the same
    position-specific presentation: four useful measures for a QB and three
    for every other supported fantasy position.  Each snapshot is cumulative
    for the game, so replacing the line on every refresh never double-counts.
    """

    normalized_position = (position or "").upper()
    if normalized_position == "QB":
        return " · ".join((
            f"{_stat_value(stats, 'pass_yards', 'passing_yards', 'PassingYards')} PASS YDS",
            f"{_stat_value(stats, 'pass_tds', 'passing_touchdowns', 'PassingTouchdowns')} PASS TD",
            f"{_stat_value(stats, 'rush_yards', 'rushing_yards', 'RushingYards')} RUSH YDS",
            f"{_stat_value(stats, 'rush_tds', 'rushing_touchdowns', 'RushingTouchdowns')} RUSH TD",
        ))
    if normalized_position == "RB":
        return " · ".join((
            f"{_stat_value(stats, 'rushing_attempts', 'rush_attempts', 'RushingAttempts')} CAR",
            f"{_stat_value(stats, 'rush_yards', 'rushing_yards', 'RushingYards')} RUSH YDS",
            f"{_stat_value(stats, 'rush_tds', 'rushing_touchdowns', 'RushingTouchdowns')} RUSH TD",
        ))
    if normalized_position in {"WR", "TE"}:
        return " · ".join((
            f"{_stat_value(stats, 'receptions', 'Receptions')} REC",
            f"{_stat_value(stats, 'rec_yards', 'receiving_yards', 'ReceivingYards')} REC YDS",
            f"{_stat_value(stats, 'rec_tds', 'receiving_touchdowns', 'ReceivingTouchdowns')} REC TD",
        ))
    if normalized_position in {"K", "PK"}:
        field_goals = _stat_value(stats, 'field_goals_made', 'fg_made', 'FGM', 'FieldGoalsMade')
        extra_points = _stat_value(stats, 'extra_points_made', 'xp_made', 'XPM', 'ExtraPointsMade')
        return f"{field_goals} FGM · {extra_points} XPM · {field_goals * 3 + extra_points} K PTS"
    return ""


def _final_game_stat_line_map(
    db: Session,
    *,
    season: int,
    week: int,
    player_ids: set[int],
    player_positions: dict[int, str | None],
) -> dict[int, str]:
    """Get one verified final box-score line per rostered player in one query."""

    if not player_ids:
        return {}
    rows = (
        db.query(PlayerGameStat)
        .filter(
            PlayerGameStat.season == season,
            PlayerGameStat.week == week,
            PlayerGameStat.player_id.in_(player_ids),
            PlayerGameStat.source == "espn_final_boxscore",
        )
        .order_by(PlayerGameStat.updated_at.desc(), PlayerGameStat.id.desc())
        .all()
    )
    lines: dict[int, str] = {}
    for row in rows:
        if row.player_id in lines:
            continue
        line = _compact_game_stat_line(row.stats or {}, player_positions.get(row.player_id))
        if line:
            lines[row.player_id] = line
    return lines


def _final_waiver_score_map(
    db: Session,
    *,
    season: int,
    week: int,
    player_ids: set[int],
    player_positions: dict[int, str | None],
    player_schools: dict[int, str | None],
    scoring_rules: dict | None,
) -> dict[int, float]:
    """Calculate completed-game waiver totals from verified box scores.

    ``PlayerWeekScore`` is intentionally scoped to roster snapshots so it
    cannot provide totals for an unrostered player.  The waiver wire instead
    reads the same verified final box score used by player game logs and
    applies this league's scoring rules at the response boundary.
    """

    if not player_ids:
        return {}
    rows = (
        db.query(PlayerGameStat)
        .filter(
            PlayerGameStat.season == season,
            PlayerGameStat.week == week,
            PlayerGameStat.player_id.in_(player_ids),
            PlayerGameStat.source == "espn_final_boxscore",
        )
        .order_by(PlayerGameStat.updated_at.desc(), PlayerGameStat.id.desc())
        .all()
    )
    scores: dict[int, float] = {}
    for row in rows:
        if row.player_id in scores:
            continue
        points, _ = calculate_player_fantasy_points(
            normalize_player_stats(row.stats or {}, player_positions.get(row.player_id)),
            scoring_rules or {},
            player_positions.get(row.player_id),
        )
        scores[row.player_id] = points
    # ESPN box scores can omit a player who appeared but recorded no counting
    # stats.  A verified final team game still makes that player's actual
    # fantasy total a meaningful zero rather than an unavailable projection.
    final_school_keys = {
        school_key
        for game in db.query(Game).filter(Game.season == season, Game.week == week).all()
        if (game.schedule_status or "").strip().lower() in {"final", "post"}
        for school_key in (_school_key(game.home_team), _school_key(game.away_team))
        if school_key
    }
    for player_id, school in player_schools.items():
        if player_id not in scores and _school_key(school) in final_school_keys:
            scores[player_id] = 0.0
    return scores


def _roster_rows(db: Session, team_id: int) -> list[RosterEntry]:
    return (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.team_id == team_id)
        .order_by(RosterEntry.slot.asc(), RosterEntry.id.asc())
        .all()
    )


def _rosters_for_teams(db: Session, team_ids: set[int]) -> dict[int, list[RosterEntry]]:
    rosters = {team_id: [] for team_id in team_ids}
    if not team_ids:
        return rosters
    entries = (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.player))
        .filter(RosterEntry.team_id.in_(team_ids))
        .order_by(RosterEntry.team_id.asc(), RosterEntry.slot.asc(), RosterEntry.id.asc())
        .all()
    )
    for entry in entries:
        rosters.setdefault(entry.team_id, []).append(entry)
    return rosters


def _injury_status_by_player(
    db: Session, *, season: int, week: int, player_ids: set[int]
) -> dict[int, str]:
    if not player_ids:
        return {}
    rows = (
        db.query(Injury)
        .filter(Injury.season == season, Injury.week == week, Injury.player_id.in_(player_ids))
        .order_by(Injury.updated_at.desc(), Injury.id.desc())
        .all()
    )
    statuses: dict[int, str] = {}
    for row in rows:
        normalized = normalize_injury_status(row.status)
        if row.player_id not in statuses and is_current_injury_designation(normalized):
            statuses[row.player_id] = normalized
    return statuses


def _serialize_roster_entry(
    roster_slot: CanonicalRosterSlot,
    league: League,
    team: Team,
    projection: WeeklyProjection | None,
    player_score: PlayerWeekScore | None = None,
    opponent: str | None = None,
    game_location: str | None = None,
    game_start_at: datetime | None = None,
    is_locked: bool = False,
    live_game: LiveGameContext | None = None,
    live_projection: LivePlayerProjection | None = None,
    scoring_rules: dict | None = None,
    injury_status: str | None = None,
    final_game_stat_line: str | None = None,
    now: datetime | None = None,
) -> RosterTabEntryRead:
    entry = roster_slot.entry
    projected = float(projection.fantasy_points) if projection and projection.fantasy_points is not None else None
    floor = float(projection.floor or 0.0) if projection else 0.0
    ceiling = float(projection.ceiling or 0.0) if projection else 0.0
    position = entry.player.position if entry and entry.player else None
    current_points = float(player_score.fantasy_points) if player_score else None
    live_final_points = None
    if live_projection is not None:
        if current_points is None:
            current_points, _ = calculate_player_fantasy_points(
                live_projection.current_stats_json or {}, scoring_rules or {}, position
            )
        live_final_points, _ = calculate_player_fantasy_points(
            live_projection.projected_final_stats_json or {}, scoring_rules or {}, position
        )
        if live_projection.projected_remaining_fantasy_points is not None and current_points is not None:
            live_final_points = round(current_points + float(live_projection.projected_remaining_fantasy_points), 2)
    kickoff_has_started = game_start_at is not None and as_utc(game_start_at) <= as_utc(now or datetime.now(timezone.utc))
    effective_game_state = (
        "final" if final_game_stat_line
        else "final" if live_game and live_game.state in {"final", "post"}
        else "live" if live_game and live_game.state == "live"
        else "final" if live_projection and live_projection.projection_status == "FINAL"
        else "live" if kickoff_has_started
        else live_game.state if live_game and live_game.state != "unavailable"
        else "live" if live_projection and live_projection.projection_status in {"LIVE", "STALE", "OUT"}
        # Preserve the existing score-feed behavior during the first accepted
        # snapshot, before its per-player projection records have been written.
        else "live" if player_score and player_score.status in {"live", "stale"}
        else "unavailable"
    )
    # The live-projection table is snapshot-keyed and stores cumulative
    # current-game totals.  Render those while a game is in progress, then
    # replace them with the verified PlayerGameStat line once it is final.
    # A published kickoff without a provider snapshot still has a truthful
    # zeroed stat line; it will be replaced on the next live refresh.
    game_stat_line = (
        final_game_stat_line
        if final_game_stat_line
        else _compact_game_stat_line(
            live_projection.current_stats_json if live_projection else {},
            position,
        )
        if effective_game_state == "live"
        else None
    )
    return RosterTabEntryRead(
        id=entry.id if entry else None,
        league_id=league.id,
        team_id=team.id,
        fantasy_team_id=team.id,
        fantasy_team_name=team.display_name,
        player_id=entry.player_id if entry else None,
        slot=roster_slot.slot_type,
        slot_id=roster_slot.slot_id,
        slot_index=roster_slot.slot_index,
        display_label=roster_slot.display_label,
        roster_slot=roster_slot.slot_type,
        injury_status=injury_status,
        status=entry.status if entry else "EMPTY",
        is_starter=roster_slot.is_starter,
        is_ir=roster_slot.is_ir,
        player_name=entry.player.name if entry and entry.player else None,
        player_school=_display_school_name(entry.player.school) if entry and entry.player else None,
        player_position=entry.player.position if entry and entry.player else None,
        school=_display_school_name(entry.player.school) if entry and entry.player else None,
        position=entry.player.position if entry and entry.player else None,
        projected_points=projected,
        floor=floor,
        ceiling=ceiling,
        boom_prob=float(projection.boom_prob or 0.0) if projection else 0.0,
        bust_prob=float(projection.bust_prob or 0.0) if projection else 0.0,
        opponent=opponent,
        game_location=game_location,
        weekly_projected_fantasy_points=projected,
        projection_status=(live_projection.projection_status if live_projection else projection.projection_status if projection else "UNAVAILABLE"),
        live_points=current_points,
        live_scoring_status=player_score.status if player_score else "unavailable",
        live_scoring_updated_at=player_score.calculated_at if player_score else None,
        current_fantasy_points=current_points,
        pregame_projected_points=projected,
        live_projected_final_points=live_final_points,
        live_projection_status=live_projection.projection_status if live_projection else None,
        live_projection_model_version=live_projection.model_version if live_projection else None,
        projection_updated_at=live_projection.calculated_at if live_projection else None,
        provider_snapshot_at=live_projection.provider_snapshot_at if live_projection else None,
        game_period=live_game.game_period if live_game and live_game.game_period is not None else live_projection.game_period if live_projection else None,
        game_clock=live_game.game_clock if live_game and live_game.game_clock is not None else live_projection.game_clock if live_projection else None,
        game_score=live_game.game_score if live_game else None,
        game_down_distance=None if live_game and live_game.game_is_halftime else live_game.game_down_distance if live_game else None,
        game_is_halftime=live_game.game_is_halftime if live_game else False,
        game_progress=live_projection.game_progress if live_projection else None,
        live_projection_fallback_reason=live_projection.fallback_reason if live_projection else None,
        live_game_state=effective_game_state,
        team_has_possession=live_game.has_possession if live_game else False,
        team_in_red_zone=live_game.in_red_zone if live_game else False,
        game_start_at=game_start_at,
        game_stat_line=game_stat_line,
        final_game_stat_line=final_game_stat_line,
        is_locked=is_locked,
    )


def _serialize_team_roster(
    db: Session,
    league: League,
    team: Team,
    week: int,
) -> list[RosterTabEntryRead]:
    entries = _roster_rows(db, team.id)
    player_ids = {entry.player_id for entry in entries}
    projection_by_player = _projection_map(
        db,
        league.season_year,
        week,
        player_ids,
    )
    score_by_player = _player_week_score_map(db, league.id, league.season_year, week, player_ids)
    player_schools = {
        entry.player_id: entry.player.school if entry.player else None
        for entry in entries
    }
    player_positions = {
        entry.player_id: entry.player.position if entry.player else None
        for entry in entries
    }
    final_game_stat_lines = _final_game_stat_line_map(
        db,
        season=league.season_year,
        week=week,
        player_ids=player_ids,
        player_positions=player_positions,
    )
    games = (
        db.query(Game).filter(Game.season == league.season_year, Game.week == week).all()
        if player_ids
        else []
    )
    live_projection_by_player = _live_projection_map(db, season=league.season_year, week=week, player_ids=player_ids) if games else {}
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first() if live_projection_by_player else None
    game_starts, opponents, game_locations = game_context_for_players(
        db,
        player_ids=player_ids,
        season=league.season_year,
        week=week,
        player_schools=player_schools,
        games=games,
    )
    live_games = _live_game_context_by_player(
        db, season=league.season_year, week=week, player_schools=player_schools, games=games
    )
    current_time = datetime.now(timezone.utc)
    slots = build_team_roster_slots(team.id, _slot_limits(db, league), entries)
    injury_statuses = _injury_status_by_player(
        db, season=league.season_year, week=week, player_ids=player_ids
    )
    return [
        _serialize_roster_entry(
            roster_slot,
            league,
            team,
            projection_by_player.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            score_by_player.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            opponents.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            game_location=game_locations.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            game_start_at=game_starts.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            live_game=live_games.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            live_projection=live_projection_by_player.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            scoring_rules=settings.scoring_json if settings else {},
            injury_status=injury_statuses.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            final_game_stat_line=final_game_stat_lines.get(roster_slot.entry.player_id) if roster_slot.entry else None,
            now=current_time,
            is_locked=(
                roster_slot.entry is not None
                and game_starts.get(roster_slot.entry.player_id) is not None
                and as_utc(game_starts[roster_slot.entry.player_id]) <= current_time
            ),
        )
        for roster_slot in slots
    ]


def _serialize_team_rosters(
    db: Session,
    league: League,
    teams: dict[int, Team],
    week: int,
) -> dict[int, list[RosterTabEntryRead]]:
    entries_by_team = _rosters_for_teams(db, set(teams))
    player_ids = {entry.player_id for entries in entries_by_team.values() for entry in entries}
    projection_by_player = _projection_map(db, league.season_year, week, player_ids)
    score_by_player = _player_week_score_map(db, league.id, league.season_year, week, player_ids)
    player_schools = {
        entry.player_id: entry.player.school if entry.player else None
        for entries in entries_by_team.values()
        for entry in entries
    }
    player_positions = {
        entry.player_id: entry.player.position if entry.player else None
        for entries in entries_by_team.values()
        for entry in entries
    }
    final_game_stat_lines = _final_game_stat_line_map(
        db,
        season=league.season_year,
        week=week,
        player_ids=player_ids,
        player_positions=player_positions,
    )
    games = (
        db.query(Game).filter(Game.season == league.season_year, Game.week == week).all()
        if player_ids
        else []
    )
    live_projection_by_player = _live_projection_map(db, season=league.season_year, week=week, player_ids=player_ids) if games else {}
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first() if live_projection_by_player else None
    game_starts, opponents, game_locations = game_context_for_players(
        db,
        player_ids=player_ids,
        season=league.season_year,
        week=week,
        player_schools=player_schools,
        games=games,
    )
    live_games = _live_game_context_by_player(
        db, season=league.season_year, week=week, player_schools=player_schools, games=games
    )
    current_time = datetime.now(timezone.utc)
    slot_limits = _slot_limits(db, league)
    injury_statuses = _injury_status_by_player(
        db, season=league.season_year, week=week, player_ids=player_ids
    )
    return {
        team_id: [
            _serialize_roster_entry(
                roster_slot,
                league,
                team,
                projection_by_player.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                score_by_player.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                opponents.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                game_location=game_locations.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                game_start_at=game_starts.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                live_game=live_games.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                live_projection=live_projection_by_player.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                scoring_rules=settings.scoring_json if settings else {},
                injury_status=injury_statuses.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                final_game_stat_line=final_game_stat_lines.get(roster_slot.entry.player_id) if roster_slot.entry else None,
                now=current_time,
                is_locked=(
                    roster_slot.entry is not None
                    and game_starts.get(roster_slot.entry.player_id) is not None
                    and as_utc(game_starts[roster_slot.entry.player_id]) <= current_time
                ),
            )
            for roster_slot in build_team_roster_slots(
                team_id,
                slot_limits,
                entries_by_team.get(team_id, []),
            )
        ]
        for team_id, team in teams.items()
    }


def _starter_projection_total(roster: list[RosterTabEntryRead]) -> float | None:
    """Sum one selected week's active starter projections, or report unavailable.

    Empty template slots do not make an otherwise populated roster invalid, but
    every actual starter must have a finite, non-negative non-BYE projection.
    That keeps the displayed total and the win-probability input on precisely
    the same weekly lineup records without fabricating missing values as zero.
    """
    total = 0.0
    starter_count = 0
    for entry in roster:
        if not entry.is_starter or entry.status == "EMPTY":
            continue
        projected_points = entry.projected_points
        if (
            entry.projection_status == "BYE"
            or projected_points is None
            or not isinstance(projected_points, (int, float))
            or not math.isfinite(projected_points)
            or projected_points < 0
        ):
            return None
        starter_count += 1
        total += float(projected_points)
    return round(total, 2) if starter_count else None


def _starter_live_totals(roster: list[RosterTabEntryRead]) -> tuple[float | None, float | None, float | None, bool]:
    """Return current, live-final, and original-pregame starter totals.

    Staggered kickoffs are handled explicitly: not-started players contribute
    zero current points but retain their pregame projection in the final total.
    """
    current = final = pregame = 0.0
    starters = 0
    any_live = False
    for entry in roster:
        if not entry.is_starter or entry.status == "EMPTY":
            continue
        starters += 1
        baseline = entry.pregame_projected_points
        if baseline is None or not math.isfinite(baseline):
            return None, None, None, any_live
        pregame += baseline
        state = (entry.live_game_state or "").lower()
        if state in {"live", "final", "post"}:
            any_live = any_live or state == "live"
            actual = entry.current_fantasy_points
            if actual is None or not math.isfinite(actual):
                return None, None, None, any_live
            current += actual
            final_value = entry.live_projected_final_points if entry.live_projected_final_points is not None else actual
            if not math.isfinite(final_value):
                return None, None, None, any_live
            final += final_value
        else:
            final += baseline
    if not starters:
        return None, None, None, any_live
    return round(current, 2), round(final, 2), round(pregame, 2), any_live


def _week_has_started(db: Session, *, season: int, week: int) -> bool:
    """Return true only when a verified non-bye kickoff has passed.

    The matchup's presentation state must be able to show actual fantasy
    points from the first kickoff, even before either fantasy lineup has a
    player in a live game. Do not infer a start from a date-only schedule row.
    """
    now = datetime.now(timezone.utc)
    return (
        db.query(TeamSchedule.id)
        .filter(
            TeamSchedule.season == season,
            TeamSchedule.week == week,
            TeamSchedule.is_bye.is_(False),
            TeamSchedule.kickoff_at.is_not(None),
            TeamSchedule.kickoff_at <= now,
        )
        .first()
        is not None
    )


def _latest_projection_metadata(*rosters: list[RosterTabEntryRead]) -> tuple[datetime | None, datetime | None]:
    rows = [entry for roster in rosters for entry in roster if entry.projection_updated_at]
    if not rows:
        return None, None
    return max((entry.projection_updated_at for entry in rows if entry.projection_updated_at), default=None), max(
        (entry.provider_snapshot_at for entry in rows if entry.provider_snapshot_at), default=None
    )


def build_roster_tab_view(
    db: Session,
    league: League,
    user: User,
    selected_week: int | None = None,
) -> LeagueRosterTabRead:
    week = resolve_current_week(db, league, selected_week)
    team = _owned_team(db, league, user)
    slot_limits = _slot_limits(db, league)
    teams = (
        db.query(Team)
        .filter(Team.league_id == league.id)
        .order_by(Team.id.asc())
        .all()
    )
    teams_by_id = {league_team.id: league_team for league_team in teams}
    rosters_by_team = _serialize_team_rosters(db, league, teams_by_id, week)
    team_records = _team_records(db, league, set(teams_by_id))
    avatars_by_owner_id = _owner_avatar_urls(db, teams, user)
    team_rosters = [
        LeagueRosterTeamRead(
            team=RosterTabTeamRead(
                id=league_team.id,
                name=league_team.display_name,
                owner_user_id=league_team.owner_user_id,
                owner_name=league_team.owner_name,
                owner_avatar_url=avatars_by_owner_id.get(league_team.owner_user_id),
                record=team_records.get(league_team.id, "0-0-0"),
            ),
            roster=rosters_by_team.get(league_team.id, []),
        )
        for league_team in teams
    ]
    if not team:
        return LeagueRosterTabRead(
            league_id=league.id,
            season=league.season_year,
            week=week,
            owned_team=None,
            roster=[],
            data=[],
            slots=[],
            roster_slot_limits=slot_limits,
            ir_slots=int(slot_limits.get("IR", 0)),
            team_rosters=team_rosters,
            message="No team found for your user in this league.",
        )

    roster = rosters_by_team.get(team.id, [])
    team_read = next((row.team for row in team_rosters if row.team.id == team.id), None)
    if team_read is None:
        team_read = _team_read(db, league, team)
    return LeagueRosterTabRead(
        league_id=league.id,
        season=league.season_year,
        week=week,
        owned_team=team_read,
        fantasy_team_id=team.id,
        fantasy_team_name=team.display_name,
        roster=roster,
        data=roster,
        slots=roster,
        roster_slot_limits=slot_limits,
        ir_slots=int(slot_limits.get("IR", 0)),
        team_rosters=team_rosters,
        message=None if roster else "Roster is empty. It will populate after the draft.",
    )


def build_matchup_tab_view(
    db: Session,
    league: League,
    user: User,
    selected_week: int | None = None,
    matchup_id: int | None = None,
) -> LeagueMatchupTabRead:
    week = resolve_current_week(db, league, selected_week)
    week_started = _week_has_started(db, season=league.season_year, week=week)
    freshness_read = LiveScoringFreshnessRead(
        state="unavailable",
    )
    # When provider polling is globally disabled, do not add a database query
    # to every matchup page solely for absent scoring state.  Shadow/enabled
    # workers opt in to the persisted ESPN freshness contract below.
    if app_settings.provider_polling_expected:
        freshness = espn_week_freshness(db, season=league.season_year, week=week)
        freshness_read = LiveScoringFreshnessRead(
            provider=freshness.provider,
            state=freshness.state,
            provider_as_of=freshness.provider_as_of,
            last_successful_update_at=freshness.last_successful_update_at,
            data_age_seconds=freshness.data_age_seconds,
            relevant_game_count=freshness.relevant_game_count,
        )
    viewer_team = _owned_team(db, league, user)
    postseason_node: PostseasonMatchup | None = None
    if matchup_id is not None:
        matchup_result = (
            db.query(Matchup, PostseasonMatchup)
            .outerjoin(PostseasonMatchup, PostseasonMatchup.fantasy_matchup_id == Matchup.id)
            .filter(
                Matchup.id == matchup_id,
                Matchup.league_id == league.id,
                Matchup.season == league.season_year,
                Matchup.week == week,
            )
            .first()
        )
        matchup, postseason_node = matchup_result if matchup_result else (None, None)
        primary_team = db.get(Team, matchup.home_team_id) if matchup else None
        opponent = db.get(Team, matchup.away_team_id) if matchup else None
    else:
        primary_team = viewer_team
        matchup_result = (
            db.query(Matchup, PostseasonMatchup)
            .outerjoin(PostseasonMatchup, PostseasonMatchup.fantasy_matchup_id == Matchup.id)
            .filter(
                Matchup.league_id == league.id,
                Matchup.season == league.season_year,
                Matchup.week == week,
                (Matchup.home_team_id == primary_team.id) | (Matchup.away_team_id == primary_team.id),
            )
            .first()
            if primary_team
            else None
        )
        matchup, postseason_node = matchup_result if matchup_result else (None, None)
        opponent_id = (
            matchup.away_team_id if matchup and matchup.home_team_id == primary_team.id else matchup.home_team_id
            if matchup and primary_team
            else None
        )
        opponent = db.get(Team, opponent_id) if opponent_id else None

    if not primary_team:
        return LeagueMatchupTabRead(
            league_id=league.id,
            season=league.season_year,
            week=week,
            week_started=week_started,
            my_roster=[],
            opponent_roster=[],
            live_scoring_freshness=freshness_read,
            message="No team found for your user in this league.",
        )

    if not matchup:
        my_roster = _serialize_team_roster(db, league, primary_team, week)
        my_total = _starter_projection_total(my_roster)
        my_team = MatchupTeamRead(
            id=primary_team.id,
            name=primary_team.display_name,
            record=_team_record(db, league, primary_team.id),
            projected_points=my_total,
            win_probability=None,
            fantasy_team_id=primary_team.id,
            fantasy_team_name=primary_team.display_name,
            manager_name=primary_team.owner_name,
            projected_total=my_total,
            current_points=0.0 if my_total is not None else None,
            pregame_projected_total=my_total,
            live_projected_total=my_total,
            roster=my_roster,
        )
        return LeagueMatchupTabRead(
            league_id=league.id,
            season=league.season_year,
            week=week,
            week_started=week_started,
            status=None,
            my_team=my_team,
            user_team=my_team if viewer_team and viewer_team.id == primary_team.id else None,
            opponent_team=None,
            my_roster=my_roster,
            opponent_roster=[],
            live_scoring_freshness=freshness_read,
            message="No matchup generated yet.",
        )

    postseason_context = (
        PostseasonMatchupContextRead(
            bracket_id=postseason_node.bracket_id,
            matchup_type=postseason_node.matchup_type,
            bracket_path=postseason_node.bracket_path,
            status=postseason_node.status,
        )
        if postseason_node is not None
        else None
    )

    roster_by_team = _serialize_team_rosters(
        db,
        league,
        {primary_team.id: primary_team, **({opponent.id: opponent} if opponent else {})},
        week,
    )
    my_roster = roster_by_team[primary_team.id]
    opponent_roster = roster_by_team.get(opponent.id, []) if opponent else []
    my_current, my_live_total, my_pregame_total, my_has_live = _starter_live_totals(my_roster)
    opponent_current, opponent_live_total, opponent_pregame_total, opponent_has_live = _starter_live_totals(opponent_roster)
    my_total = my_live_total if my_has_live else my_pregame_total
    opponent_total = opponent_live_total if opponent_has_live else opponent_pregame_total
    my_probability, opponent_probability = calculate_matchup_win_probability(
        my_total,
        opponent_total,
    ) or (None, None)

    record_team_ids = {primary_team.id}
    if opponent:
        record_team_ids.add(opponent.id)
    records = _team_records(db, league, record_team_ids)
    avatars_by_owner_id = _owner_avatar_urls(
        db,
        [team for team in (primary_team, opponent) if team is not None],
        user,
    )
    my_team = MatchupTeamRead(
        id=primary_team.id,
        name=primary_team.display_name,
        record=records[primary_team.id],
        projected_points=my_total,
        win_probability=my_probability,
        fantasy_team_id=primary_team.id,
        fantasy_team_name=primary_team.display_name,
        manager_name=primary_team.owner_name,
        owner_avatar_url=avatars_by_owner_id.get(primary_team.owner_user_id),
        projected_total=my_total,
        current_points=my_current,
        pregame_projected_total=my_pregame_total,
        live_projected_total=my_live_total,
        roster=my_roster,
    )
    opponent_team = (
        MatchupTeamRead(
            id=opponent.id,
            name=opponent.display_name,
            record=records[opponent.id],
            projected_points=opponent_total,
            win_probability=opponent_probability,
            fantasy_team_id=opponent.id,
            fantasy_team_name=opponent.display_name,
            manager_name=opponent.owner_name,
            owner_avatar_url=avatars_by_owner_id.get(opponent.owner_user_id),
            projected_total=opponent_total,
            current_points=opponent_current,
            pregame_projected_total=opponent_pregame_total,
            live_projected_total=opponent_live_total,
            roster=opponent_roster,
        )
        if opponent
        else None
    )
    projection_updated_at, provider_snapshot_at = _latest_projection_metadata(my_roster, opponent_roster)
    # A bench player's kickoff must activate the page refresh timer and live
    # row treatment too. Starter-only values above remain the sole authority
    # for the fantasy matchup total.
    any_rostered_game_live = any(
        (entry.live_game_state or "").lower() == "live"
        for entry in [*my_roster, *opponent_roster]
    )
    effective_status = "live" if any_rostered_game_live or my_has_live or opponent_has_live else matchup.status
    return LeagueMatchupTabRead(
        league_id=league.id,
        season=league.season_year,
        week=week,
        week_started=week_started,
        matchup_id=matchup.id,
        status=effective_status,
        my_team=my_team,
        user_team=my_team if viewer_team and viewer_team.id == primary_team.id else None,
        opponent_team=opponent_team,
        my_roster=my_roster,
        opponent_roster=opponent_roster,
        projection_source="live_projection_v1" if projection_updated_at else "weekly_projections",
        live_scoring_freshness=freshness_read,
        projection_updated_at=projection_updated_at,
        provider_snapshot_at=provider_snapshot_at,
        next_refresh_at=(provider_snapshot_at + timedelta(seconds=180)) if provider_snapshot_at else None,
        message=None,
        rivalry=matchup_rivalry_context(db, league, matchup, primary_team, opponent),
        postseason=postseason_context,
    )


def build_waivers_view(
    db: Session,
    league: League,
    user: User,
    limit: int = 50,
    offset: int = 0,
    selected_week: int | None = None,
) -> LeagueWaiversRead:
    week = resolve_current_week(db, league, selected_week)
    team = _owned_team(db, league, user)
    unavailable_player_ids = {
        player_id
        for (player_id,) in db.query(RosterEntry.player_id)
        .filter(RosterEntry.league_id == league.id)
        .all()
    }
    # Availability is league-roster scoped. A drafted player is unavailable only
    # while they are still rostered; once dropped, they re-enter the league's
    # waiver/free-agent lifecycle. Excluding every DraftPick here made the UI
    # show a different pool than the claim service validates.
    eligible_players = db.query(Player).filter(
        ~Player.id.in_(unavailable_player_ids),
        canonical_fantasy_player_filter(league.season_year),
    ).all()
    player_ids = {player.id for player in eligible_players}
    availability_by_player = {
        row.player_id: row
        for row in db.query(PlayerWaiverAvailability)
        .filter(
            PlayerWaiverAvailability.league_id == league.id,
            PlayerWaiverAvailability.player_id.in_(player_ids or {0}),
        )
        .all()
    }
    projection_by_player = _projection_map(db, league.season_year, week, player_ids)
    player_positions = {player.id: player.position for player in eligible_players}
    player_schools = {player.id: player.school for player in eligible_players}
    game_starts_by_player, opponent_by_player, _locations_by_player = game_context_for_players(
        db,
        player_ids=player_ids,
        season=league.season_year,
        week=week,
        player_schools=player_schools,
    )
    claims = []
    roster = []
    waiver_priority = None
    faab_remaining = None
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    final_score_by_player = _final_waiver_score_map(
        db,
        season=league.season_year,
        week=week,
        player_ids=player_ids,
        player_positions=player_positions,
        player_schools=player_schools,
        scoring_rules=settings.scoring_json if settings else {},
    )
    now = datetime.now(timezone.utc)
    waiver_state = waiver_window_state(db, league, settings, now=now) if settings else None
    availability_states = waiver_player_availability_states(
        db,
        league=league,
        player_ids=player_ids,
        now=now,
        settings=settings,
        player_schools=player_schools,
        availability_by_player=availability_by_player,
        game_starts_by_player=game_starts_by_player,
    )
    current_period = (
        db.query(WaiverPeriod)
        .filter(
            WaiverPeriod.league_id == league.id,
            WaiverPeriod.season == league.season_year,
            WaiverPeriod.status.in_(("scheduled", "open", "locked")),
        )
        .order_by(WaiverPeriod.processes_at.asc(), WaiverPeriod.id.asc())
        .first()
    )
    results_period = (
        db.query(WaiverPeriod)
        .filter(
            WaiverPeriod.league_id == league.id,
            WaiverPeriod.status == "completed",
        )
        .order_by(WaiverPeriod.processed_at.desc(), WaiverPeriod.processes_at.desc(), WaiverPeriod.id.desc())
        .first()
    )
    completed_claim_rows = (
        db.query(WaiverClaim)
        .filter(
            WaiverClaim.league_id == league.id,
            WaiverClaim.waiver_period_id == results_period.id if results_period else False,
            WaiverClaim.status == "won",
        )
        .order_by(WaiverClaim.processed_at.desc(), WaiverClaim.id.desc())
        .limit(12)
        .all()
        if results_period
        else []
    )
    if team:
        priority_row = (
            db.query(WaiverPriority)
            .filter(WaiverPriority.league_id == league.id, WaiverPriority.team_id == team.id)
            .first()
        )
        waiver_priority = priority_row.priority if priority_row else None
        faab_remaining = priority_row.faab_remaining if priority_row else (settings.faab_starting_budget if settings else 100)
        claim_rows = (
            db.query(WaiverClaim)
            .filter(WaiverClaim.league_id == league.id, WaiverClaim.team_id == team.id)
            .order_by(
                (WaiverClaim.status == "pending").desc(),
                WaiverClaim.preference_order.asc(),
                WaiverClaim.created_at.desc(),
                WaiverClaim.id.desc(),
            )
            .limit(25)
            .all()
        )
        claims = serialize_claims(db, claim_rows)
        roster = [
            WaiverDropCandidateRead(
                roster_entry_id=entry.id,
                player_id=entry.player_id,
                player_name=entry.player.name if entry.player else "Unknown Player",
                position=entry.player.position if entry.player else None,
                school=entry.player.school if entry.player else None,
                slot=entry.slot,
            )
            for entry in _roster_rows(db, team.id)
        ]
    def availability_for_player(player_id: int) -> tuple[str, datetime | None]:
        return availability_states[player_id]

    def projection_for_player(player_id: int) -> tuple[float | None, str]:
        projection = projection_by_player.get(player_id)
        if projection is None:
            return None, "UNAVAILABLE"
        status = projection.projection_status.upper()
        if status == "BYE":
            return None, "BYE"
        return float(projection.fantasy_points), status

    def waiver_sort_key(player: Player) -> tuple[int, float, float, str, int]:
        projected, projection_status = projection_for_player(player.id)
        if projected is not None and projected > 0:
            state = 0
        elif projected is not None:
            state = 1
        elif projection_status == "BYE":
            state = 2
        else:
            state = 3
        canonical_rank = float(player.sheet_adp) if player.sheet_adp is not None else float("inf")
        return (state, -(projected or 0.0), canonical_rank, player.name.casefold(), player.id)

    ordered_players = sorted(eligible_players, key=waiver_sort_key)
    total = len(ordered_players)
    players = ordered_players[offset : offset + limit]

    return LeagueWaiversRead(
        league_id=league.id,
        fantasy_team_id=team.id if team else None,
        waiver_priority=waiver_priority,
        faab_remaining=faab_remaining,
        available_players=[
            LeagueWaiverPlayerRead(
                id=player.id,
                name=player.name,
                school=player.school,
                opponent=opponent_by_player.get(player.id),
                position=player.position,
                weekly_projected_fantasy_points=projection_for_player(player.id)[0],
                final_fantasy_points=final_score_by_player.get(player.id),
                projection_status=projection_for_player(player.id)[1],
                availability_state=availability_for_player(player.id)[0],
                available_at=availability_for_player(player.id)[1],
            )
            for player in players
        ],
        claims=claims,
        current_period=_serialize_waiver_period(current_period),
        results_period=_serialize_waiver_period(results_period),
        results=serialize_claims(db, completed_claim_rows),
        roster=roster,
        waiver_rules={
            "waiver_type": settings.waiver_type if settings else "faab",
            "waiver_period_hours": settings.waiver_period_hours if settings else 24,
            "faab_budget": settings.faab_starting_budget if settings else 100,
            "allow_zero_faab_bids": settings.allow_zero_faab_bids if settings else True,
            "reveal_all_waiver_bids": settings.reveal_all_waiver_bids if settings else False,
            "processing_weekday": settings.waiver_processing_weekday if settings else 6,
            "processing_hour": settings.waiver_processing_hour if settings else 8,
            "timezone": settings.waiver_timezone if settings else "America/New_York",
            "post_drop_waiver_hours": settings.post_drop_waiver_hours if settings else 24,
            "phase": waiver_state.mode if waiver_state else "waivers",
            "next_process_at": waiver_state.next_process_at.isoformat() if waiver_state else None,
            "last_processed_at": waiver_state.last_processed_at.isoformat() if waiver_state and waiver_state.last_processed_at else None,
        },
        total_available=total,
        message=None if team else "No team found for your user in this league.",
    )


def build_settings_view(db: Session, league: League, user: User) -> LeagueSettingsViewRead:
    from collegefootballfantasy_api.app.models.postseason import LeaguePostseasonSettings
    from collegefootballfantasy_api.app.services.postseason_topology import required_rounds

    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    postseason_settings = (
        db.query(LeaguePostseasonSettings)
        .filter(
            LeaguePostseasonSettings.league_id == league.id,
            LeaguePostseasonSettings.season == league.season_year,
        )
        .one_or_none()
    )
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()
    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.id.asc()).all()
    teams_by_id = {team.id: team for team in teams}
    roster_by_team = _serialize_team_rosters(
        db,
        league,
        {team.id: team for team in teams},
        resolve_current_week(db, league),
    )
    roster_rows = [entry for roster in roster_by_team.values() for entry in roster]
    standings = [
        row.model_dump()
        for row in build_standings_summary(db, league)
    ]
    schedule_rows = (
        db.query(Matchup, Team.id)
        .join(Team, Team.id == Matchup.home_team_id)
        .filter(Matchup.league_id == league.id, Matchup.season == league.season_year)
        .order_by(Matchup.week.asc(), Matchup.id.asc())
        .all()
    )
    away_names = {team.id: team.display_name for team in teams}
    schedule = [
        LeagueScheduleRowRead(
            matchup_id=matchup.id,
            week=matchup.week,
            home_team_id=matchup.home_team_id,
            home_team_name=away_names.get(home_team_id, "TBD"),
            away_team_id=matchup.away_team_id,
            away_team_name=away_names.get(matchup.away_team_id, "TBD"),
            home_projected_total=float(matchup.home_score or 0.0),
            away_projected_total=float(matchup.away_score or 0.0),
            home_win_probability=50.0,
            away_win_probability=50.0,
        )
        for matchup, home_team_id in schedule_rows
    ]
    draft = db.query(Draft).filter(Draft.league_id == league.id).first()
    draft_status = (draft.status if draft else None) or league.status
    draft_is_complete = (draft_status or "").lower() in {"completed", "complete", "final", "closed"} or league.status == "post_draft"
    active_invite = (
        db.query(LeagueInvite)
        .filter(LeagueInvite.league_id == league.id, LeagueInvite.active.is_(True))
        .order_by(LeagueInvite.created_at.desc(), LeagueInvite.id.desc())
        .first()
    )
    invite_code = league.invite_code or (active_invite.code if active_invite else None)
    invite = None
    if league.commissioner_user_id == user.id and invite_code and not draft_is_complete:
        invite = LeagueInviteSettingsRead(
            code=invite_code,
            link=f"{app_settings.ui_base_url.rstrip('/')}/join/{invite_code}",
            draft_status=draft_status,
            visible_until_draft_complete=True,
        )
    draft_results: list[dict] = []
    if draft:
        pick_rows = (
            db.query(DraftPick, Team, Player)
            .join(Team, Team.id == DraftPick.team_id)
            .join(Player, Player.id == DraftPick.player_id)
            .filter(DraftPick.draft_id == draft.id)
            .order_by(DraftPick.overall_pick.asc())
            .all()
        )
        draft_results = [
            {
                "overall_pick": pick.overall_pick,
                "round_number": pick.round_number,
                "round_pick": pick.round_pick,
                "team_id": team.id,
                "team_name": team.display_name,
                "player_id": player.id,
                "player_name": player.name,
                "position": player.position,
            }
            for pick, team, player in pick_rows
        ]

    completed_trades = (
        db.query(TradeOffer)
        .options(joinedload(TradeOffer.items).joinedload(TradeOfferItem.player))
        .filter(
            TradeOffer.league_id == league.id,
            TradeOffer.status == "processed",
        )
        .order_by(TradeOffer.processed_at.desc().nullslast(), TradeOffer.id.desc())
        .all()
    )

    def trade_party(team_id: int) -> LeagueTradeHistoryPartyRead:
        team = teams_by_id.get(team_id)
        return LeagueTradeHistoryPartyRead(
            team_id=team_id,
            team_name=team.display_name if team else "Unknown team",
            manager_name=team.owner_name if team else None,
        )

    def trade_assets(offer: TradeOffer, team_id: int) -> list[LeagueTradeHistoryAssetRead]:
        return [
            LeagueTradeHistoryAssetRead(
                player_id=item.player_id,
                name=(item.player.name if item.player else "Draft pick"),
                position=item.player.position if item.player else None,
                school=item.player.school if item.player else None,
            )
            for item in sorted(offer.items, key=lambda row: row.id)
            if item.team_id == team_id
        ]

    trade_history = [
        LeagueTradeHistoryRead(
            id=offer.id,
            status=offer.status,
            proposing_party=trade_party(offer.proposing_team_id),
            receiving_party=trade_party(offer.receiving_team_id),
            proposing_team_sends=trade_assets(offer, offer.proposing_team_id),
            receiving_team_sends=trade_assets(offer, offer.receiving_team_id),
            created_at=offer.created_at,
            accepted_at=offer.accepted_at,
            processed_at=offer.processed_at,
        )
        for offer in completed_trades
    ]

    return LeagueSettingsViewRead(
        league_id=league.id,
        league_name=league.name,
        league_info={
            "name": league.name,
            "season": league.season_year,
            "status": league.status,
            "max_teams": league.max_teams,
            "is_private": league.is_private,
            "commissioner_user_id": league.commissioner_user_id,
        },
        postseason_calendar=(
            {
                "regular_season_start_week": postseason_settings.regular_season_start_week,
                "regular_season_end_week": postseason_settings.regular_season_end_week,
                "playoff_start_week": postseason_settings.playoff_start_week,
                "championship_week": postseason_settings.championship_week,
                "playoff_teams": postseason_settings.playoff_team_count,
                "max_rounds": required_rounds(postseason_settings.playoff_team_count),
                "calendar_policy_version": postseason_settings.calendar_policy_version,
                "source_identity": postseason_settings.calendar_source_identity,
                "source_revision": postseason_settings.calendar_source_revision,
                "source_sha256": postseason_settings.calendar_source_sha256,
                "source_format_version": postseason_settings.calendar_source_format_version,
            }
            if postseason_settings is not None
            else None
        ),
        invite=invite,
        members=[LeagueMemberRead.model_validate(member) for member in members],
        teams=[
            LeagueWorkspaceTeamRead(
                id=team.id,
                league_id=team.league_id,
                name=team.display_name,
                owner_user_id=team.owner_user_id,
            )
            for team in teams
        ],
        scoring_settings=settings.scoring_json if settings else {},
        roster_settings=settings.roster_slots_json if settings and settings.roster_slots_json else DEFAULT_ROSTER_SLOTS.copy(),
        waiver_rules={
            "waiver_type": settings.waiver_type if settings else "FAAB",
            "waiver_period_hours": settings.waiver_period_hours if settings else 24,
            "trade_review_type": settings.trade_review_type if settings else "commissioner",
        },
        standings=standings,
        schedule=schedule,
        rosters=roster_rows,
        trade_history=trade_history,
        draft_results=draft_results,
        commissioner_controls=(
            ["reschedule_draft", "update_settings", "regenerate_invite"]
            if league.commissioner_user_id == user.id
            else []
        ),
    )
