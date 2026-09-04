from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any

import httpx
from sqlalchemy import and_, case, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.integrations.conference_availability_reports import (
    ConferenceAvailabilityReportClient,
    ConferenceReportUnavailable,
    report_source_for,
)
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.cfb_standing_snapshot import CFBStandingSnapshot
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.models.player_news_event import PlayerNewsEvent
from collegefootballfantasy_api.app.models.player_weekly_context import PlayerWeeklyContext
from collegefootballfantasy_api.app.services.notification_service import log_official_injury_update
from collegefootballfantasy_api.app.services.player_trade_value import calculate_player_trade_value
from collegefootballfantasy_api.app.services.availability_corrections import (
    has_active_manual_override,
    publish_zero_projection_for_unavailable_player,
)
from collegefootballfantasy_api.app.services.power4 import (
    conference_for_school,
    list_power4_teams,
    normalize_school,
    resolve_power4_school,
)
from collegefootballfantasy_api.app.services.provider_identity import (
    upsert_player_provider_mapping,
    upsert_team_provider_mapping,
)

_OFFENSE_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


def _pick_str(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _pick_int(row: dict[str, Any], *keys: str) -> int | None:
    value = _pick_str(row, *keys)
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _normalize_status(raw_status: str | None) -> str:
    status = (raw_status or "FULL").upper()
    if any(
        token in status
        for token in ("OUT FOR SEASON", "SEASON ENDING", "SEASON-ENDING", "SEASON END", "LOST FOR THE SEASON")
    ):
        return "OUT_FOR_SEASON"
    if "OUT" in status:
        return "OUT"
    if "DOUBTFUL" in status:
        return "DOUBTFUL"
    if "QUESTION" in status or "GTD" in status or "GAME-TIME" in status:
        return "QUESTIONABLE"
    if "PROBABLE" in status:
        return "PROBABLE"
    return "FULL"


_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _timeline_indicates_four_or_more_weeks(timeline: str | None) -> bool:
    """Apply the product's IR threshold only when a report is explicit."""
    text = (timeline or "").lower().strip()
    if not text:
        return False
    if any(phrase in text for phrase in ("out for season", "season-ending", "season ending", "lost for the season")):
        return True
    if re.search(r"(?:at least|minimum of|more than)\s+(?:4|four)\s+(?:weeks?|wks?|games?)", text):
        return True
    numeric_range = re.search(r"\b(\d+)\s*(?:-|to)\s*(\d+)\s*(?:weeks?|wks?|games?)\b", text)
    if numeric_range:
        return int(numeric_range.group(1)) >= 4
    numeric_duration = re.search(r"\b(\d+)\s*(?:weeks?|wks?|games?)\b", text)
    if numeric_duration:
        return int(numeric_duration.group(1)) >= 4
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\s*(?:weeks?|wks?|games?)\b", text):
            return value >= 4
    return bool(re.search(r"\b(?:one|1)\s+month\b", text))


def _official_availability_status(raw_status: str | None, timeline: str | None) -> str:
    raw = (raw_status or "").upper()
    if "IR" in raw or "INJURED RESERVE" in raw:
        return "IR"
    if _timeline_indicates_four_or_more_weeks(f"{raw} {timeline or ''}"):
        return "IR"
    if "OUT" in raw:
        return "OUT"
    if "DOUBTFUL" in raw or "QUESTION" in raw or "GAME-TIME" in raw:
        return "QUESTIONABLE"
    if "AVAILABLE" in raw or "ACTIVE" in raw or "PROBABLE" in raw:
        return "FULL"
    return "FULL"


def _availability_multiplier(status: str) -> tuple[float, float]:
    if status in {"OUT", "IR"}:
        return 0.0, 0.0
    if status == "QUESTIONABLE":
        return 0.7, 0.7
    return 1.0, 1.0


def _availability_hash(row: dict[str, str | None], status: str) -> str:
    values = (
        row.get("player_name"), row.get("team_name"), row.get("position"), status,
        row.get("injury"), row.get("return_timeline"), row.get("practice_level"),
        row.get("notes"), row.get("source_url"),
    )
    return sha256("\x1f".join(value or "" for value in values).encode()).hexdigest()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def sync_power4_players_from_sportsdata(db: Session) -> dict[str, int]:
    if not settings.sportsdata_enabled:
        raise RuntimeError("SPORTSDATA_ENABLED is false")
    client = SportsDataClient()
    rows = client.get_players()

    created = 0
    updated = 0
    skipped = 0

    for row in rows:
        external_id = _pick_str(row, "PlayerID", "PlayerId", "ID", "Id")
        name = _pick_str(row, "Name", "PlayerName", "FullName")
        position = (_pick_str(row, "Position", "Pos") or "UNK").upper()
        team_candidate = _pick_str(row, "TeamName", "School", "College", "Team", "TeamKey")
        canonical_team = resolve_power4_school(team_candidate or "")

        if not name or not canonical_team or position not in _OFFENSE_POSITIONS:
            skipped += 1
            continue

        provider_team_id = _pick_str(row, "TeamID", "TeamId", "Team", "TeamKey")

        existing: Player | None = None
        if external_id:
            existing = db.scalar(select(Player).where(Player.external_id == external_id))
        if not existing:
            existing = db.scalar(
                select(Player).where(
                    and_(
                        Player.name == name,
                        Player.school == canonical_team,
                        Player.position == position,
                    )
                )
            )

        if existing:
            existing.name = name
            existing.school = canonical_team
            existing.position = position
            if external_id:
                existing.external_id = external_id
            db.add(existing)
            db.flush()
            if external_id:
                upsert_player_provider_mapping(
                    db,
                    player_id=existing.id,
                    provider="sportsdata",
                    provider_player_id=external_id,
                    provider_team_id=provider_team_id,
                    match_confidence=1.0,
                    verification_status="unverified",
                    reason="sportsdata player sync",
                )
            if provider_team_id:
                upsert_team_provider_mapping(
                    db,
                    team_name=canonical_team,
                    provider="sportsdata",
                    provider_team_id=provider_team_id,
                    provider_team_name=team_candidate,
                )
            updated += 1
            continue

        player = Player(
            external_id=external_id,
            name=name,
            school=canonical_team,
            position=position,
        )
        db.add(player)
        db.flush()
        if external_id:
            upsert_player_provider_mapping(
                db,
                player_id=player.id,
                provider="sportsdata",
                provider_player_id=external_id,
                provider_team_id=provider_team_id,
                match_confidence=1.0,
                verification_status="unverified",
                reason="sportsdata player sync",
            )
        if provider_team_id:
            upsert_team_provider_mapping(
                db,
                team_name=canonical_team,
                provider="sportsdata",
                provider_team_id=provider_team_id,
                provider_team_name=team_candidate,
            )
        created += 1

    db.flush()
    return {"created": created, "updated": updated, "skipped": skipped}


def sync_power4_schedule_from_sportsdata(db: Session, season: int) -> dict[str, int]:
    if not settings.sportsdata_enabled:
        raise RuntimeError("SPORTSDATA_ENABLED is false")
    client = SportsDataClient()
    rows = client.get_schedule(season=season)

    created = 0
    updated = 0
    skipped = 0
    affected_weeks: set[int] = set()

    for row in rows:
        week_value = _pick_int(row, "Week", "GameWeek")
        # Week 0 is a real player-game period for early teams. It is never a
        # fantasy league week, so notification/lineup reconciliation below is
        # intentionally restricted to positive league weeks.
        if week_value is None or week_value < 0:
            skipped += 1
            continue
        affected_weeks.add(week_value)

        home_raw = _pick_str(row, "HomeTeamName", "HomeTeam", "HomeSchool")
        away_raw = _pick_str(row, "AwayTeamName", "AwayTeam", "AwaySchool")
        resolved_home = resolve_power4_school(home_raw or "")
        resolved_away = resolve_power4_school(away_raw or "")
        # Keep a Power Four team's real non-P4 opener in the canonical game
        # table. The previous all-P4 requirement silently discarded exactly
        # the early Week 0 games whose player results we need to retain.
        if not resolved_home and not resolved_away:
            skipped += 1
            continue
        home_team = resolved_home or (home_raw or "").strip()
        away_team = resolved_away or (away_raw or "").strip()
        if not home_team or not away_team:
            skipped += 1
            continue

        external_id = _pick_str(row, "GameID", "GameId", "GlobalGameID")
        if not external_id:
            external_id = f"{season}:{week_value}:{home_team}:{away_team}"

        game = db.scalar(select(Game).where(Game.external_id == external_id))
        if not game:
            game = Game(
                external_id=external_id,
                season=season,
                week=week_value,
            )
            created += 1
        else:
            updated += 1

        season_type_raw = (_pick_str(row, "SeasonType", "GameType") or "regular").lower()
        season_type = "postseason" if "post" in season_type_raw else "regular"
        game.season = season
        game.week = week_value
        game.season_type = season_type
        game.schedule_status = _pick_str(row, "Status", "GameStatus", "StatusCode")
        game.start_date = _parse_datetime(_pick_str(row, "DateTime", "Day", "Date"))
        game.home_team = home_team
        game.away_team = away_team
        game.home_points = _pick_int(row, "HomeScore", "HomePoints")
        game.away_points = _pick_int(row, "AwayScore", "AwayPoints")
        game.neutral_site = (_pick_int(row, "NeutralVenue", "NeutralSite") or 0) == 1
        db.add(game)

    db.flush()
    # Schedule data is the verified kickoff source used by locked lineup
    # snapshots. Reconcile only affected weeks; this queues/cancels durable
    # events and never sends provider HTTP from the sync transaction.
    from collegefootballfantasy_api.app.services.notification_service import rebuild_matchup_start_notifications_for_schedule

    rebuild_matchup_start_notifications_for_schedule(
        db,
        season=season,
        weeks={week for week in affected_weeks if week > 0},
    )
    return {"created": created, "updated": updated, "skipped": skipped}


def sync_power4_standings_from_sportsdata(
    db: Session,
    *,
    season: int,
    conference: str,
) -> list[CFBStandingSnapshot]:
    if not settings.sportsdata_enabled:
        raise RuntimeError("SPORTSDATA_ENABLED is false")

    client = SportsDataClient()
    rows = client.get_standings(season=season)
    conference_key = conference.upper().replace(" ", "")
    teams = set(list_power4_teams(conference_key))
    if not teams:
        return []

    parsed_rows: dict[str, dict[str, int | None]] = {}
    for row in rows:
        team_name = resolve_power4_school(
            _pick_str(row, "TeamName", "School", "Name", "Team", "Key") or ""
        )
        if not team_name or team_name not in teams:
            continue

        parsed_rows[team_name] = {
            "conference_rank": _pick_int(row, "ConferenceRank", "Rank"),
            "conference_wins": _pick_int(row, "ConferenceWins", "ConfWins"),
            "conference_losses": _pick_int(row, "ConferenceLosses", "ConfLosses"),
            "overall_wins": _pick_int(row, "Wins", "OverallWins"),
            "overall_losses": _pick_int(row, "Losses", "OverallLosses"),
        }

    if not parsed_rows:
        return []

    return upsert_power4_standings_snapshot(
        db,
        season=season,
        conference=conference_key,
        rows=parsed_rows,
        source="sportsdata",
    )


def _normalize_injury_rows_for_ingest(
    rows: list[dict[str, Any]],
    *,
    source: str,
) -> list[dict[str, str | None]]:
    normalized: list[dict[str, str | None]] = []
    for row in rows:
        player_name = _pick_str(row, "Player", "Name", "PlayerName", "FullName")
        team_raw = _pick_str(row, "TeamName", "School", "Team", "College")
        team_name = resolve_power4_school(team_raw or "")
        if not player_name or not team_name:
            continue

        status = _normalize_status(_pick_str(row, "Status", "InjuryStatus", "GameStatus"))
        normalized.append(
            {
                "player_name": player_name,
                "team_name": team_name,
                "position": (_pick_str(row, "Position", "Pos") or "UNK").upper(),
                "status": status,
                "injury": _pick_str(row, "Injury", "BodyPart", "InjuryBodyPart", "Title"),
                "return_timeline": _pick_str(
                    row,
                    "ExpectedReturn",
                    "ReturnDate",
                    "Timeline",
                    "Expected Return",
                ),
                "practice_level": _pick_str(
                    row,
                    "PracticeStatus",
                    "PracticeParticipation",
                    "Practice",
                ),
                "notes": _pick_str(row, "Notes", "Comment", "Headline"),
                "external_id": _pick_str(row, "PlayerID", "PlayerId"),
                "source": source,
            }
        )
    return normalized


def _upsert_power4_injuries(
    db: Session,
    *,
    season: int,
    week: int,
    conference: str | None,
    rows: list[dict[str, str | None]],
) -> dict[str, int]:
    conference_key = conference.upper().replace(" ", "") if conference else None

    existing_rows = (
        db.query(Injury, Player)
        .join(Player, Player.id == Injury.player_id)
        .filter(Injury.season == season, Injury.week == week)
        .all()
    )
    existing_by_player_id: dict[int, Injury] = {}
    scoped_existing_player_ids: set[int] = set()
    for injury, player in existing_rows:
        conf = conference_for_school(player.school or "")
        if conf is None:
            continue
        if conference_key and conf != conference_key:
            continue
        existing_by_player_id[player.id] = injury
        scoped_existing_player_ids.add(player.id)

    seen_player_ids: set[int] = set()
    created = 0
    updated = 0

    for row in rows:
        conference_name = conference_for_school(row["team_name"] or "")
        if conference_name is None:
            continue
        if conference_key and conference_name != conference_key:
            continue

        player = None
        external_id = row.get("external_id")
        if external_id:
            player = db.scalar(select(Player).where(Player.external_id == external_id))
        if not player:
            player = db.scalar(
                select(Player).where(
                    and_(
                        Player.name == row["player_name"],
                        Player.school == row["team_name"],
                    )
                )
            )
        if not player:
            player = Player(
                external_id=external_id,
                name=row["player_name"] or "Unknown",
                school=row["team_name"] or "Unknown",
                position=row["position"] or "UNK",
            )
            db.add(player)
            db.flush()
        else:
            if row["position"] and player.position != row["position"]:
                player.position = row["position"] or player.position
            if row["team_name"] and player.school != row["team_name"]:
                player.school = row["team_name"] or player.school
            if external_id and not player.external_id:
                player.external_id = external_id
            db.add(player)

        seen_player_ids.add(player.id)
        existing = existing_by_player_id.get(player.id)
        if existing:
            existing.status = row["status"] or existing.status
            existing.injury = row["injury"]
            existing.return_timeline = row["return_timeline"]
            existing.practice_level = row["practice_level"]
            existing.notes = row["notes"]
            existing.is_game_time_decision = "QUESTIONABLE" == (row["status"] or "").upper()
            db.add(existing)
            updated += 1
            continue

        db.add(
            Injury(
                player_id=player.id,
                season=season,
                week=week,
                status=row["status"] or "FULL",
                injury=row["injury"],
                return_timeline=row["return_timeline"],
                practice_level=row["practice_level"],
                is_game_time_decision="QUESTIONABLE" == (row["status"] or "").upper(),
                is_returning=False,
                notes=row["notes"],
            )
        )
        created += 1

    removed = 0
    for player_id in scoped_existing_player_ids - seen_player_ids:
        row = existing_by_player_id.get(player_id)
        if row:
            db.delete(row)
            removed += 1

    db.flush()
    return {"created": created, "updated": updated, "removed": removed}


def _upsert_official_availability_rows(
    db: Session,
    *,
    season: int,
    week: int,
    rows: list[dict[str, str | None]],
) -> dict[str, int]:
    """Persist only exact, in-product P4 player matches from official reports."""
    eligible_players = db.query(Player).filter(Player.position.in_(sorted(_OFFENSE_POSITIONS))).all()
    players_by_identity = {
        (normalize_school(player.name), normalize_school(player.school)): player
        for player in eligible_players
        if conference_for_school(player.school or "")
    }
    current_injuries = {
        injury.player_id: injury
        for injury in db.query(Injury).filter(Injury.season == season, Injury.week == week).all()
    }
    created = updated = unchanged = skipped = events_created = overrides_preserved = 0
    value_refresh_player_ids: set[int] = set()

    for row in rows:
        school = resolve_power4_school(row.get("team_name") or "")
        source_position = (row.get("position") or "").upper().strip()
        if not school or (source_position and source_position not in _OFFENSE_POSITIONS):
            skipped += 1
            continue
        player = players_by_identity.get((normalize_school(row.get("player_name") or ""), normalize_school(school)))
        if player is None or player.position.upper() not in _OFFENSE_POSITIONS:
            skipped += 1
            continue
        if source_position and source_position != player.position.upper():
            skipped += 1
            continue

        status = _official_availability_status(row.get("status"), row.get("return_timeline"))
        content_hash = _availability_hash(row, status)
        probability_active, multiplier = _availability_multiplier(status)
        existing = current_injuries.get(player.id)
        # A reviewed manual/team report is intentionally allowed to beat an
        # older or incomplete conference report, but only for the weeks it
        # explicitly covers.  Once the window ends, normal official sync
        # resumes automatically.
        if has_active_manual_override(db, player_id=player.id, season=season, week=week):
            overrides_preserved += 1
            continue
        semantic_change = (
            existing is None
            or existing.status != status
            or existing.injury != row.get("injury")
            or existing.return_timeline != row.get("return_timeline")
            or existing.practice_level != row.get("practice_level")
            or existing.notes != row.get("notes")
        )
        if existing is None:
            existing = Injury(
                player_id=player.id, season=season, week=week, status=status,
                injury=row.get("injury"), return_timeline=row.get("return_timeline"),
                practice_level=row.get("practice_level"),
                is_game_time_decision=status == "QUESTIONABLE",
                is_returning=status == "FULL", notes=row.get("notes"),
            )
            db.add(existing)
            current_injuries[player.id] = existing
            created += 1
            value_refresh_player_ids.add(player.id)
        elif semantic_change:
            existing.status = status
            existing.injury = row.get("injury")
            existing.return_timeline = row.get("return_timeline")
            existing.practice_level = row.get("practice_level")
            existing.is_game_time_decision = status == "QUESTIONABLE"
            existing.is_returning = status == "FULL"
            existing.notes = row.get("notes")
            db.add(existing)
            updated += 1
            value_refresh_player_ids.add(player.id)
        else:
            # A policy multiplier may change without the official report row
            # changing. Repair the current-week cache in place without emitting
            # duplicate news or notifications for an unchanged availability
            # report.
            availability_event = (
                db.query(PlayerAvailabilityEvent)
                .filter(
                    PlayerAvailabilityEvent.player_id == player.id,
                    PlayerAvailabilityEvent.season == season,
                    PlayerAvailabilityEvent.week == week,
                    PlayerAvailabilityEvent.content_hash == content_hash,
                )
                .order_by(PlayerAvailabilityEvent.id.desc())
                .first()
            )
            if availability_event is not None:
                availability_event.probability_active = probability_active
                availability_event.availability_multiplier = multiplier
                db.add(availability_event)
            context = db.query(PlayerWeeklyContext).filter(
                PlayerWeeklyContext.player_id == player.id,
                PlayerWeeklyContext.season == season,
                PlayerWeeklyContext.week == week,
            ).first()
            if context is not None:
                context.availability_multiplier = multiplier
                db.add(context)
            unchanged += 1
            continue

        notes = " • ".join(
            value for value in (
                row.get("injury"), row.get("practice_level"), row.get("return_timeline"), row.get("notes")
            ) if value
        ) or None
        event = PlayerAvailabilityEvent(
            player_id=player.id, season=season, week=week, status=status,
            probability_active=probability_active, availability_multiplier=multiplier,
            source=f"official_{row.get('conference', 'conference').lower()}_availability_report",
            source_url=row.get("source_url"), content_hash=content_hash,
            source_reliability=1.0, published_at=datetime.now(timezone.utc),
            effective_from_week=week, reviewed=True, notes=notes,
        )
        db.add(event)
        db.flush()
        db.add(
            PlayerNewsEvent(
                player_id=player.id, season=season, week=week, event_type="AVAILABILITY",
                source=event.source, source_url=event.source_url, content_hash=content_hash,
                source_reliability=1.0, published_at=event.published_at,
                effective_from_week=week, reviewed=True,
                notes=event.notes or f"Official status: {status}",
            )
        )
        context = db.query(PlayerWeeklyContext).filter(
            PlayerWeeklyContext.player_id == player.id,
            PlayerWeeklyContext.season == season,
            PlayerWeeklyContext.week == week,
        ).first()
        if context is not None:
            context.availability_status = status
            context.availability_multiplier = multiplier
            context.availability_event_id = event.id
            context.reviewed = True
            context.change_reason = f"official conference availability report: {status}"
            db.add(context)
        publish_zero_projection_for_unavailable_player(
            db, player=player, season=season, week=week, status=status,
            note=event.notes or f"Official status: {status}",
        )
        log_official_injury_update(
            db, player=player, season=season, week=week, status=status,
            content_hash=content_hash, source_url=row.get("source_url"), detail=event.notes,
        )
        events_created += 1

    db.flush()
    # Publish the same availability adjustment used by player cards and trade
    # analysis to the general player payload immediately after an official
    # status changes. This keeps list, roster, draft, and card values aligned.
    for player_id in value_refresh_player_ids:
        player = db.get(Player, player_id)
        if player is not None and player.raw_cfb27_rating is not None:
            calculate_player_trade_value(db, player_id=player_id, season=season, week=week)
    db.flush()
    return {
        "created": created, "updated": updated, "unchanged": unchanged,
        "skipped": skipped, "events_created": events_created,
        "overrides_preserved": overrides_preserved,
    }


def sync_power4_injuries(
    db: Session,
    *,
    season: int,
    week: int,
    conference: str | None = None,
) -> dict[str, int | str]:
    """Sync public official conference reports; RotoWire is never a fallback."""
    conferences = [conference.upper().replace(" ", "")] if conference else ["SEC", "ACC", "BIG12", "BIG10"]
    client = ConferenceAvailabilityReportClient()
    source_rows: list[dict[str, str | None]] = []
    unavailable: list[str] = []
    for conference_key in conferences:
        source = report_source_for(conference_key)
        try:
            source_rows.extend(client.get_rows(source))
        except (httpx.HTTPError, ConferenceReportUnavailable) as exc:
            unavailable.append(f"{conference_key}: {exc}")
    if unavailable and len(unavailable) == len(conferences) and not source_rows:
        raise RuntimeError("; ".join(unavailable))
    changes = _upsert_official_availability_rows(db, season=season, week=week, rows=source_rows)
    result: dict[str, int | str] = {
        **changes,
        "source": "official_conference_reports",
        "rows_seen": len(source_rows),
    }
    if unavailable:
        result["provider_error"] = "; ".join(unavailable)
    return result


def upsert_power4_standings_snapshot(
    db: Session,
    *,
    season: int,
    conference: str,
    rows: dict[str, dict[str, int | None]],
    source: str,
) -> list[CFBStandingSnapshot]:
    conference_key = conference.upper().replace(" ", "")
    db.query(CFBStandingSnapshot).filter(
        CFBStandingSnapshot.season == season,
        CFBStandingSnapshot.conference == conference_key,
    ).delete(synchronize_session=False)

    output: list[CFBStandingSnapshot] = []
    for team_name in list_power4_teams(conference_key):
        row = rows.get(team_name, {})
        record = CFBStandingSnapshot(
            team_name=team_name,
            conference=conference_key,
            season=season,
            conference_rank=row.get("conference_rank"),
            conference_wins=row.get("conference_wins"),
            conference_losses=row.get("conference_losses"),
            overall_wins=row.get("overall_wins"),
            overall_losses=row.get("overall_losses"),
            source=source,
        )
        db.add(record)
        output.append(record)

    db.flush()
    return output


def read_power4_standings_snapshot(
    db: Session,
    *,
    season: int,
    conference: str,
) -> list[CFBStandingSnapshot]:
    conference_key = conference.upper().replace(" ", "")
    rows = (
        db.query(CFBStandingSnapshot)
        .filter(
            CFBStandingSnapshot.season == season,
            CFBStandingSnapshot.conference == conference_key,
        )
        .order_by(
            case((CFBStandingSnapshot.conference_rank.is_(None), 1), else_=0),
            CFBStandingSnapshot.conference_rank.asc(),
            CFBStandingSnapshot.team_name.asc(),
        )
        .all()
    )
    return rows
