from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, case, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.integrations.rotowire import RotowireClient
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.cfb_standing_snapshot import CFBStandingSnapshot
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury, InjuryHistory
from collegefootballfantasy_api.app.models.injury_impact import InjuryImpact
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.injury_impact import injury_projection_delta
from collegefootballfantasy_api.app.services.injury_normalization import (
    display_injury_status,
    injury_is_active,
    normalize_injury_status,
    parse_source_datetime,
)
from collegefootballfantasy_api.app.services.injury_sync import notify_injury_change
from collegefootballfantasy_api.app.services.power4 import (
    conference_for_school,
    list_power4_teams,
    resolve_power4_school,
)
from collegefootballfantasy_api.app.services.provider_identity_audit import (
    provider_player_index,
    upsert_player_provider_id,
)
from collegefootballfantasy_api.app.services.team_provider_mapping import upsert_team_provider_id

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
    return display_injury_status(raw_status)


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
    players_by_provider_id = provider_player_index(db, "sportsdata")

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

        existing: Player | None = None
        if external_id:
            existing = players_by_provider_id.get(external_id)
        if not existing and external_id:
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
                upsert_player_provider_id(
                    db,
                    player_id=existing.id,
                    provider="sportsdata",
                    provider_player_id=external_id,
                    provider_team_id=_pick_str(row, "TeamID", "TeamId", "TeamKey", "Team"),
                    match_confidence=100,
                )
            db.add(existing)
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
            upsert_player_provider_id(
                db,
                player_id=player.id,
                provider="sportsdata",
                provider_player_id=external_id,
                provider_team_id=_pick_str(row, "TeamID", "TeamId", "TeamKey", "Team"),
                match_confidence=100,
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

    for row in rows:
        week_value = _pick_int(row, "Week", "GameWeek")
        if week_value is None or week_value <= 0:
            skipped += 1
            continue

        home_raw = _pick_str(row, "HomeTeamName", "HomeTeam", "HomeSchool")
        away_raw = _pick_str(row, "AwayTeamName", "AwayTeam", "AwaySchool")
        home_team = resolve_power4_school(home_raw or "")
        away_team = resolve_power4_school(away_raw or "")
        if not home_team or not away_team:
            skipped += 1
            continue
        home_provider_team_id = _pick_str(row, "HomeTeamID", "HomeTeamId", "HomeTeamKey", "HomeTeam")
        away_provider_team_id = _pick_str(row, "AwayTeamID", "AwayTeamId", "AwayTeamKey", "AwayTeam")
        home_abbreviation = _pick_str(row, "HomeTeam", "HomeTeamKey", "HomeTeamAbbreviation")
        away_abbreviation = _pick_str(row, "AwayTeam", "AwayTeamKey", "AwayTeamAbbreviation")

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
        game.provider = "sportsdata"
        game.season_type = season_type
        game.start_date = _parse_datetime(_pick_str(row, "DateTime", "Day", "Date"))
        game.home_team = home_team
        game.away_team = away_team
        game.home_provider_team_id = home_provider_team_id
        game.away_provider_team_id = away_provider_team_id
        game.home_points = _pick_int(row, "HomeScore", "HomePoints")
        game.away_points = _pick_int(row, "AwayScore", "AwayPoints")
        game.neutral_site = (_pick_int(row, "NeutralVenue", "NeutralSite") or 0) == 1
        db.add(game)
        if home_provider_team_id:
            upsert_team_provider_id(
                db,
                canonical_school=home_team,
                provider="sportsdata",
                provider_team_id=home_provider_team_id,
                provider_team_name=home_raw,
                provider_abbreviation=home_abbreviation,
            )
        if away_provider_team_id:
            upsert_team_provider_id(
                db,
                canonical_school=away_team,
                provider="sportsdata",
                provider_team_id=away_provider_team_id,
                provider_team_name=away_raw,
                provider_abbreviation=away_abbreviation,
            )

    db.flush()
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
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        player_name = _pick_str(row, "Player", "Name", "PlayerName", "FullName")
        team_raw = _pick_str(row, "TeamName", "School", "Team", "College")
        team_name = resolve_power4_school(team_raw or "")
        if not player_name or not team_name:
            continue

        raw_status = _pick_str(row, "Status", "InjuryStatus", "GameStatus")
        status = _normalize_status(raw_status)
        body_part = _pick_str(row, "BodyPart", "InjuryBodyPart", "Injury")
        normalized.append(
            {
                "player_name": player_name,
                "team_name": team_name,
                "position": (_pick_str(row, "Position", "Pos") or "UNK").upper(),
                "status": status,
                "normalized_status": normalize_injury_status(raw_status),
                "injury": _pick_str(row, "Injury", "Title", "BodyPart", "InjuryBodyPart"),
                "body_part": body_part,
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
                "source_updated_at": parse_source_datetime(
                    _pick_str(row, "Updated", "UpdatedAt", "LastUpdated", "DateTime", "Timestamp")
                ),
                "source": source,
            }
        )
    return normalized


def _upsert_injury_history(
    db: Session,
    *,
    injury: Injury,
    source_updated_at: datetime | None,
) -> None:
    existing = (
        db.query(InjuryHistory)
        .filter(
            InjuryHistory.player_id == injury.player_id,
            InjuryHistory.season == injury.season,
            InjuryHistory.week == injury.week,
            InjuryHistory.status == injury.status,
            InjuryHistory.injury == injury.injury,
            InjuryHistory.source == injury.source,
        )
        .first()
    )
    if existing:
        existing.normalized_status = injury.normalized_status
        existing.body_part = injury.body_part
        existing.return_timeline = injury.return_timeline
        existing.practice_level = injury.practice_level
        existing.notes = injury.notes
        existing.source_updated_at = source_updated_at or existing.source_updated_at
        db.add(existing)
        return
    db.add(
        InjuryHistory(
            player_id=injury.player_id,
            season=injury.season,
            week=injury.week,
            status=injury.status,
            normalized_status=injury.normalized_status,
            injury=injury.injury,
            body_part=injury.body_part,
            return_timeline=injury.return_timeline,
            practice_level=injury.practice_level,
            notes=injury.notes,
            source=injury.source,
            source_updated_at=source_updated_at,
        )
    )


def _upsert_injury_impact(
    db: Session,
    *,
    injury: Injury,
    projection_points: float | None,
) -> None:
    delta, multiplier, confidence, reason = injury_projection_delta(
        projection_points,
        injury.normalized_status,
    )
    impact = (
        db.query(InjuryImpact)
        .filter(
            InjuryImpact.player_id == injury.player_id,
            InjuryImpact.season == injury.season,
            InjuryImpact.week == injury.week,
        )
        .first()
    )
    if not impact:
        impact = InjuryImpact(
            player_id=injury.player_id,
            season=injury.season,
            week=injury.week,
        )
    impact.delta_fpts = delta
    impact.multiplier = multiplier
    impact.confidence = confidence
    impact.reason = reason
    db.add(impact)


def _upsert_power4_injuries(
    db: Session,
    *,
    season: int,
    week: int,
    conference: str | None,
    rows: list[dict[str, Any]],
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

    projection_by_player = {
        projection.player_id: projection
        for projection in db.query(WeeklyProjection)
        .filter(WeeklyProjection.season == season, WeeklyProjection.week == week)
        .all()
    }
    seen_player_ids: set[int] = set()
    created = 0
    updated = 0
    cleared = 0
    notifications = 0
    now = datetime.now(timezone.utc)
    sportsdata_player_index = provider_player_index(db, "sportsdata")

    for row in rows:
        conference_name = conference_for_school(row["team_name"] or "")
        if conference_name is None:
            continue
        if conference_key and conference_name != conference_key:
            continue

        player = None
        external_id = row.get("external_id")
        if external_id:
            player = sportsdata_player_index.get(str(external_id))
        if not player and external_id:
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
            if external_id:
                upsert_player_provider_id(
                    db,
                    player_id=player.id,
                    provider="sportsdata",
                    provider_player_id=str(external_id),
                    provider_team_id=row.get("team_name"),
                    match_confidence=90,
                )
                sportsdata_player_index[str(external_id)] = player
        else:
            if row["position"] and player.position != row["position"]:
                player.position = row["position"] or player.position
            if row["team_name"] and player.school != row["team_name"]:
                player.school = row["team_name"] or player.school
            if external_id and not player.external_id:
                player.external_id = external_id
            if external_id:
                upsert_player_provider_id(
                    db,
                    player_id=player.id,
                    provider="sportsdata",
                    provider_player_id=str(external_id),
                    provider_team_id=row.get("team_name"),
                    match_confidence=90,
                )
            db.add(player)

        seen_player_ids.add(player.id)
        normalized_status = row.get("normalized_status") or normalize_injury_status(row.get("status"))
        source_updated_at = row.get("source_updated_at")
        projection_points = (
            projection_by_player[player.id].fantasy_points
            if player.id in projection_by_player
            else player.sheet_projected_season_points
        )
        existing = existing_by_player_id.get(player.id)
        if existing:
            old_status = existing.status
            existing.status = row["status"] or existing.status
            existing.normalized_status = normalized_status
            existing.injury = row["injury"]
            existing.body_part = row.get("body_part")
            existing.return_timeline = row["return_timeline"]
            existing.practice_level = row["practice_level"]
            existing.notes = row["notes"]
            existing.source = row.get("source") or existing.source or "unknown"
            existing.source_updated_at = source_updated_at or existing.source_updated_at
            existing.first_seen_at = existing.first_seen_at or now
            existing.last_seen_at = now
            existing.cleared_at = None if injury_is_active(normalized_status) else now
            existing.is_game_time_decision = normalized_status == "questionable"
            db.add(existing)
            _upsert_injury_history(db, injury=existing, source_updated_at=source_updated_at)
            _upsert_injury_impact(db, injury=existing, projection_points=projection_points)
            notifications += notify_injury_change(
                db,
                player_id=player.id,
                player_name=player.name,
                old_status=old_status,
                new_status=existing.status,
                injury_id=existing.id,
            )
            updated += 1
            continue

        injury = Injury(
            player_id=player.id,
            season=season,
            week=week,
            status=row["status"] or "HEALTHY",
            normalized_status=normalized_status,
            injury=row["injury"],
            body_part=row.get("body_part"),
            return_timeline=row["return_timeline"],
            practice_level=row["practice_level"],
            is_game_time_decision=normalized_status == "questionable",
            is_returning=False,
            notes=row["notes"],
            source=row.get("source") or "unknown",
            source_updated_at=source_updated_at,
            first_seen_at=now,
            last_seen_at=now,
            cleared_at=None if injury_is_active(normalized_status) else now,
        )
        db.add(injury)
        db.flush()
        _upsert_injury_history(db, injury=injury, source_updated_at=source_updated_at)
        _upsert_injury_impact(db, injury=injury, projection_points=projection_points)
        notifications += notify_injury_change(
            db,
            player_id=player.id,
            player_name=player.name,
            old_status=None,
            new_status=injury.status,
            injury_id=injury.id,
        )
        created += 1

    for player_id in scoped_existing_player_ids - seen_player_ids:
        row = existing_by_player_id.get(player_id)
        if row:
            old_status = row.status
            row.status = "HEALTHY"
            row.normalized_status = "healthy"
            row.last_seen_at = now
            row.cleared_at = row.cleared_at or now
            db.add(row)
            _upsert_injury_history(db, injury=row, source_updated_at=row.source_updated_at)
            _upsert_injury_impact(
                db,
                injury=row,
                projection_points=(
                    projection_by_player[player_id].fantasy_points
                    if player_id in projection_by_player
                    else None
                ),
            )
            notifications += notify_injury_change(
                db,
                player_id=player_id,
                player_name="Player",
                old_status=old_status,
                new_status=row.status,
                injury_id=row.id,
            )
            cleared += 1

    db.flush()
    return {"created": created, "updated": updated, "cleared": cleared, "notifications": notifications}


def sync_power4_injuries(
    db: Session,
    *,
    season: int,
    week: int,
    conference: str | None = None,
) -> dict[str, int | str]:
    source = "sportsdata"
    provider_error: str | None = None

    normalized_rows: list[dict[str, Any]] = []
    if settings.sportsdata_enabled:
        try:
            provider_rows = SportsDataClient().get_injuries(season=season)
            normalized_rows = _normalize_injury_rows_for_ingest(provider_rows, source="sportsdata")
        except Exception as exc:  # pragma: no cover - provider network failures are environment-specific
            provider_error = str(exc)

    if not normalized_rows:
        source = "rotowire"
        fallback_rows = RotowireClient().get_injuries()
        normalized_rows = _normalize_injury_rows_for_ingest(fallback_rows, source="rotowire")

    changes = _upsert_power4_injuries(
        db,
        season=season,
        week=week,
        conference=conference,
        rows=normalized_rows,
    )
    result: dict[str, int | str] = {
        **changes,
        "source": source,
        "rows_seen": len(normalized_rows),
    }
    if provider_error:
        result["provider_error"] = provider_error
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
