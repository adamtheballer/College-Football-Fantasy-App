from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, select
from sqlalchemy.orm import Session

from api.app.core.config import settings
from api.app.integrations.cfbd import CFBDClient
from api.app.integrations.rotowire import RotowireClient
from api.app.integrations.sportsdata import SportsDataClient
from api.app.models.cfb_standing_snapshot import CFBStandingSnapshot
from api.app.models.game import Game
from api.app.models.injury import Injury
from api.app.models.player import Player
from api.app.services.power4 import (
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


def _compose_player_name(row: dict[str, Any]) -> str | None:
    first_name = _pick_str(row, "FirstName", "First", "GivenName")
    last_name = _pick_str(row, "LastName", "Last", "Surname")
    if first_name and last_name:
        return f"{first_name} {last_name}".strip()
    return first_name or last_name


def _normalize_player_lookup_name(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in (value or ""))
    text = " ".join(text.split())
    if not text:
        return ""
    parts = text.split(" ")
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
    if parts and parts[-1] in suffix_map:
        parts[-1] = suffix_map[parts[-1]]
    return " ".join(parts)


def _name_parts(normalized_name: str) -> tuple[str, str] | None:
    parts = normalized_name.split(" ")
    if not parts:
        return None
    first = parts[0]
    last = parts[-1]
    if not first or not last:
        return None
    return first, last


def normalize_player_class_label(raw_class: str | None) -> str | None:
    if not raw_class:
        return None
    value = " ".join(str(raw_class).strip().replace("-", " ").replace("_", " ").split())
    if not value:
        return None
    key = value.lower()
    class_map = {
        "fr": "FR",
        "freshman": "FR",
        "rs fr": "RS-FR",
        "rs freshman": "RS-FR",
        "redshirt freshman": "RS-FR",
        "so": "SO",
        "sophomore": "SO",
        "rs so": "RS-SO",
        "rs sophomore": "RS-SO",
        "redshirt sophomore": "RS-SO",
        "jr": "JR",
        "junior": "JR",
        "rs jr": "RS-JR",
        "rs junior": "RS-JR",
        "redshirt junior": "RS-JR",
        "sr": "SR",
        "senior": "SR",
        "rs sr": "RS-SR",
        "rs senior": "RS-SR",
        "redshirt senior": "RS-SR",
        "graduate": "GR",
        "grad": "GR",
        "graduate student": "GR",
        "rs graduate": "RS-GR",
        "redshirt graduate": "RS-GR",
    }
    normalized = class_map.get(key)
    if normalized:
        return normalized
    return value.upper()


def _normalize_offense_position(value: str | None) -> str | None:
    position = (value or "").strip().upper()
    if position in _OFFENSE_POSITIONS:
        return position
    mapped = {
        "HB": "RB",
        "TB": "RB",
        "FB": "RB",
        "ATH": "WR",
    }.get(position)
    return mapped


def _class_label_from_year_number(year_number: int) -> str:
    if year_number <= 1:
        return "FR"
    if year_number == 2:
        return "SO"
    if year_number == 3:
        return "JR"
    if year_number == 4:
        return "SR"
    return "GR"


def build_power4_player_class_lookup_from_cfbd(
    *,
    target_season: int | None = None,
) -> dict[tuple[str, str, str], str]:
    if not settings.cfbd_api_key:
        return {}

    now_year = datetime.now().year
    desired_season = target_season or now_year
    candidate_source_seasons = [desired_season, desired_season - 1, desired_season - 2]

    client = CFBDClient()
    source_season: int | None = None
    for season in candidate_source_seasons:
        if season <= 0:
            continue
        try:
            probe = client._request("roster", params={"year": season, "team": "Ohio State"})
        except Exception:
            continue
        if isinstance(probe, list) and probe:
            source_season = season
            break

    if source_season is None:
        return {}

    season_delta = desired_season - source_season
    lookup: dict[tuple[str, str, str], str] = {}
    for team in list_power4_teams():
        try:
            roster_rows = client._request("roster", params={"year": source_season, "team": team})
        except Exception:
            continue
        if not isinstance(roster_rows, list):
            continue

        canonical_team = resolve_power4_school(team) or team
        for row in roster_rows:
            first_name = _pick_str(row, "firstName", "FirstName", "first", "First")
            last_name = _pick_str(row, "lastName", "LastName", "last", "Last")
            name = _pick_str(row, "name", "Name")
            if not name:
                if first_name and last_name:
                    name = f"{first_name} {last_name}".strip()
                else:
                    name = first_name or last_name
            normalized_position = _normalize_offense_position(_pick_str(row, "position", "Position"))
            if not name or not normalized_position:
                continue

            raw_year = _pick_int(row, "year", "Year")
            if raw_year is None:
                continue
            adjusted_year = max(1, min(6, raw_year + season_delta))
            class_label = _class_label_from_year_number(adjusted_year)
            lookup[(_normalize_player_lookup_name(name), normalized_position, canonical_team)] = class_label

    return lookup


def build_power4_player_class_lookup_from_sportsdata() -> dict[tuple[str, str, str], str]:
    if not settings.sportsdata_enabled:
        return {}

    client = SportsDataClient()
    rows = client.get_players()
    team_id_to_school, team_code_to_school = _build_power4_team_lookup(client)
    lookup: dict[tuple[str, str, str], str] = {}

    for row in rows:
        name = _pick_str(row, "Name", "PlayerName", "FullName") or _compose_player_name(row)
        position = (_pick_str(row, "Position", "Pos") or "").upper()
        raw_class = _pick_str(row, "Class", "ClassYear", "Year", "AcademicYear")
        normalized_class = normalize_player_class_label(raw_class)
        if not name or not position or not normalized_class:
            continue
        if position not in _OFFENSE_POSITIONS:
            continue

        team_id = _pick_int(row, "TeamID", "TeamId")
        team_code = _pick_str(row, "Team", "TeamKey")
        team_candidate = _pick_str(row, "TeamName", "School", "College")
        if not team_candidate and team_id is not None:
            team_candidate = team_id_to_school.get(team_id)
        if not team_candidate and team_code:
            team_candidate = team_code_to_school.get(team_code)
        canonical_team = resolve_power4_school(team_candidate or "")
        if not canonical_team:
            continue

        key = (_normalize_player_lookup_name(name), position, canonical_team)
        # Keep the first resolved class to avoid oscillation from duplicate provider rows.
        if key not in lookup:
            lookup[key] = normalized_class

    return lookup


def backfill_power4_player_classes_from_lookup(
    db: Session,
    class_lookup: dict[tuple[str, str, str], str],
) -> dict[str, int]:
    if not class_lookup:
        return {"updated": 0, "missing": 0}

    by_name_pos: dict[tuple[str, str], str] = {}
    collisions: set[tuple[str, str]] = set()
    by_school_pos_last_initial: dict[tuple[str, str, str, str], str] = {}
    fuzzy_collisions: set[tuple[str, str, str, str]] = set()
    for (normalized_name, position, _school), class_label in class_lookup.items():
        key = (normalized_name, position)
        existing = by_name_pos.get(key)
        if existing is None:
            by_name_pos[key] = class_label
        elif existing != class_label:
            collisions.add(key)
    for (normalized_name, position, school), class_label in class_lookup.items():
        name_parts = _name_parts(normalized_name)
        if not name_parts:
            continue
        first, last = name_parts
        fuzzy_key = (school, position, last, first[:1])
        existing = by_school_pos_last_initial.get(fuzzy_key)
        if existing is None:
            by_school_pos_last_initial[fuzzy_key] = class_label
        elif existing != class_label:
            fuzzy_collisions.add(fuzzy_key)
    for key in collisions:
        by_name_pos.pop(key, None)
    for key in fuzzy_collisions:
        by_school_pos_last_initial.pop(key, None)

    updated = 0
    missing = 0
    players = db.query(Player).filter(Player.position.in_(tuple(_OFFENSE_POSITIONS))).all()
    for player in players:
        current = (player.player_class or "").strip()
        if current:
            continue

        normalized_name = _normalize_player_lookup_name(player.name)
        canonical_school = resolve_power4_school(player.school or "") or (player.school or "")
        key = (normalized_name, (player.position or "").upper(), canonical_school)
        class_label = class_lookup.get(key)
        if not class_label:
            class_label = by_name_pos.get((normalized_name, (player.position or "").upper()))
        if not class_label:
            name_parts = _name_parts(normalized_name)
            if name_parts:
                first, last = name_parts
                class_label = by_school_pos_last_initial.get(
                    (canonical_school, (player.position or "").upper(), last, first[:1])
                )
        if class_label:
            player.player_class = class_label
            db.add(player)
            updated += 1
        else:
            missing += 1

    db.flush()
    return {"updated": updated, "missing": missing}


def _build_power4_team_lookup(client: SportsDataClient) -> tuple[dict[int, str], dict[str, str]]:
    team_id_to_school: dict[int, str] = {}
    team_code_to_school: dict[str, str] = {}
    current_year = datetime.now().year
    seasons = (current_year - 1, current_year, current_year + 1)

    for season in seasons:
        try:
            schedule_rows = client.get_schedule(season=season)
        except Exception:
            continue

        for row in schedule_rows:
            for side in ("Home", "Away"):
                team_id = _pick_int(row, f"{side}TeamID")
                team_code = _pick_str(row, f"{side}Team")
                team_name = _pick_str(row, f"{side}TeamName", f"{side}School")
                canonical_team = resolve_power4_school(team_name or "")
                if not canonical_team:
                    continue
                if team_id is not None:
                    team_id_to_school[team_id] = canonical_team
                if team_code:
                    team_code_to_school[team_code] = canonical_team

    return team_id_to_school, team_code_to_school


def _normalize_image_url(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("//"):
        return f"https:{text}"
    if text.startswith("http://") or text.startswith("https://"):
        return text
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
    team_id_to_school, team_code_to_school = _build_power4_team_lookup(client)

    created = 0
    updated = 0
    skipped = 0
    class_lookup: dict[tuple[str, str, str], str] = {}

    for row in rows:
        external_id = _pick_str(row, "PlayerID", "PlayerId", "ID", "Id")
        name = _pick_str(row, "Name", "PlayerName", "FullName") or _compose_player_name(row)
        position = (_pick_str(row, "Position", "Pos") or "UNK").upper()
        player_class = normalize_player_class_label(_pick_str(row, "Class", "ClassYear", "Year", "AcademicYear"))
        image_url = _normalize_image_url(
            _pick_str(
                row,
                "PhotoUrl",
                "PhotoURL",
                "HeadshotUrl",
                "HeadshotURL",
                "Headshot",
                "Photo",
                "ImageUrl",
                "ImageURL",
            )
        )
        team_id = _pick_int(row, "TeamID", "TeamId")
        team_code = _pick_str(row, "Team", "TeamKey")
        team_candidate = _pick_str(row, "TeamName", "School", "College")
        if not team_candidate and team_id is not None:
            team_candidate = team_id_to_school.get(team_id)
        if not team_candidate and team_code:
            team_candidate = team_code_to_school.get(team_code)
        canonical_team = resolve_power4_school(team_candidate or "")

        if not name or not canonical_team or position not in _OFFENSE_POSITIONS:
            skipped += 1
            continue
        if player_class:
            class_lookup[(_normalize_player_lookup_name(name), position, canonical_team)] = player_class

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
        if not existing:
            normalized_name = _normalize_player_lookup_name(name)
            candidates = (
                db.query(Player)
                .filter(
                    and_(
                        Player.position == position,
                        Player.school == canonical_team,
                    )
                )
                .all()
            )
            for candidate in candidates:
                if _normalize_player_lookup_name(candidate.name) == normalized_name:
                    existing = candidate
                    break

        if existing:
            existing.name = name
            existing.school = canonical_team
            existing.position = position
            if external_id:
                existing.external_id = external_id
            if image_url:
                existing.image_url = image_url
            if player_class:
                existing.player_class = player_class
            db.add(existing)
            updated += 1
            continue

        db.add(
            Player(
                external_id=external_id,
                name=name,
                school=canonical_team,
                position=position,
                image_url=image_url,
                player_class=player_class,
            )
        )
        created += 1

    class_backfill = backfill_power4_player_classes_from_lookup(db, class_lookup)
    db.flush()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "class_backfilled": class_backfill["updated"],
        "class_missing": class_backfill["missing"],
    }


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
    team_id_to_school: dict[int, str] | None = None,
    team_code_to_school: dict[str, str] | None = None,
) -> list[dict[str, str | None]]:
    team_id_to_school = team_id_to_school or {}
    team_code_to_school = team_code_to_school or {}
    normalized: list[dict[str, str | None]] = []
    for row in rows:
        player_name = (
            _pick_str(row, "Player", "Name", "PlayerName", "FullName")
            or _compose_player_name(row)
        )
        team_id = _pick_int(row, "TeamID", "TeamId")
        team_code = _pick_str(row, "Team", "TeamKey")
        team_raw = _pick_str(row, "TeamName", "School", "College", "Team")
        team_name = resolve_power4_school(team_raw or "")
        if not team_name and team_id is not None:
            team_name = team_id_to_school.get(team_id)
        if not team_name and team_code:
            team_name = team_code_to_school.get(team_code)
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
    fallback_error: str | None = None

    normalized_rows: list[dict[str, str | None]] = []
    if settings.sportsdata_enabled:
        try:
            client = SportsDataClient()
            provider_rows = client.get_injuries(season=season)
            team_id_to_school, team_code_to_school = _build_power4_team_lookup(client)
            normalized_rows = _normalize_injury_rows_for_ingest(
                provider_rows,
                source="sportsdata",
                team_id_to_school=team_id_to_school,
                team_code_to_school=team_code_to_school,
            )
        except Exception as exc:  # pragma: no cover - provider network failures are environment-specific
            provider_error = str(exc)

    if not normalized_rows:
        source = "rotowire"
        try:
            fallback_rows = RotowireClient().get_injuries()
            normalized_rows = _normalize_injury_rows_for_ingest(fallback_rows, source="rotowire")
        except Exception as exc:  # pragma: no cover - fallback network failures are environment-specific
            fallback_error = str(exc)

    if not normalized_rows and provider_error and fallback_error:
        result: dict[str, int | str] = {
            "created": 0,
            "updated": 0,
            "removed": 0,
            "source": "unavailable",
            "rows_seen": 0,
            "provider_error": provider_error,
            "fallback_error": fallback_error,
        }
        return result

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
    if fallback_error:
        result["fallback_error"] = fallback_error
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
