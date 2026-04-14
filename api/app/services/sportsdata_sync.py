from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.integrations.rotowire import RotowireClient
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.cfb_standing_snapshot import CFBStandingSnapshot
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.power4 import (
    conference_for_school,
    list_power4_teams,
    resolve_power4_school,
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
        for token in (
            "OUT FOR SEASON",
            "SEASON ENDING",
            "SEASON-ENDING",
            "SEASON END",
            "LOST FOR THE SEASON",
        )
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
            updated += 1
            continue

        db.add(
            Player(
                external_id=external_id,
                name=name,
                school=canonical_team,
                position=position,
            )
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
        game.start_date = _parse_datetime(_pick_str(row, "DateTime", "Day", "Date"))
        game.home_team = home_team
        game.away_team = away_team
        game.home_points = _pick_int(row, "HomeScore", "HomePoints")
        game.away_points = _pick_int(row, "AwayScore", "AwayPoints")
        game.neutral_site = (_pick_int(row, "NeutralVenue", "NeutralSite") or 0) == 1
        db.add(game)

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


def sync_power4_injuries(
    db: Session,
    *,
    season: int,
    week: int,
    conference: str | None = None,
) -> dict[str, int | str]:
    source = "sportsdata"
    provider_error: str | None = None

    normalized_rows: list[dict[str, str | None]] = []
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
