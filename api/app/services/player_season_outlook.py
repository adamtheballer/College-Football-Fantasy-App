"""Deterministic, locally sourced player-season outlook generation.

Player-card reads only retrieve persisted rows. Generation is an explicit
batch operation and has no HTTP or LLM dependency.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.player_season_context import PlayerSeasonContext
from collegefootballfantasy_api.app.models.player_season_outlook import PlayerSeasonOutlook
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.services.player_bio import normalize_sheet_player_class


PLAYER_OUTLOOK_GENERATOR_VERSION = "PLAYER_OUTLOOK_V1"
PLAYER_OUTLOOK_FACTS_VERSION = "PLAYER_OUTLOOK_FACTS_V1"
PRESEASON_OUTLOOK_TYPE = "PRESEASON"
READY = "READY"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
FAILED_VALIDATION = "FAILED_VALIDATION"
SUPPORTED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


@dataclass(frozen=True)
class GeneratedOutlook:
    facts: dict[str, Any]
    text: str | None
    status: str
    validation_errors: list[str]


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _finite(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _class_label(player: Player) -> str:
    value = normalize_sheet_player_class(player.sheet_bio_class) or _clean(player.player_class)
    return value or "current"


def _history_summary(row: PlayerHistoricalSeasonStat | None, position: str) -> dict[str, Any] | None:
    if row is None:
        return None
    values: dict[str, Any] = {
        "season": row.season,
        "team": _clean(row.team_name),
        "provider": row.provider,
        "import_version": _clean(row.import_version),
        "imported_at": row.imported_at.isoformat() if row.imported_at else None,
        "source_response_hash": _clean(row.source_response_hash),
        "games_played": row.games_played,
        "games_started": row.games_started,
        "fantasy_points": _finite(row.fantasy_points),
        "fantasy_points_per_game": _finite(row.fantasy_points_per_game),
    }
    if position == "QB":
        values.update(passing_yards=_finite(row.passing_yards), passing_touchdowns=_finite(row.passing_touchdowns))
    elif position == "RB":
        values.update(rushing_yards=_finite(row.rushing_yards), rushing_touchdowns=_finite(row.rushing_touchdowns))
    elif position in {"WR", "TE"}:
        values.update(receptions=_finite(row.receptions), receiving_yards=_finite(row.receiving_yards), receiving_touchdowns=_finite(row.receiving_touchdowns))
    elif position == "K":
        values.update(field_goals_made=_finite(row.field_goals_made), extra_points_made=_finite(row.extra_points_made))
    return values


def _meaningful_history(row: PlayerHistoricalSeasonStat, position: str) -> bool:
    summary = _history_summary(row, position) or {}
    ignored = {"season", "team", "provider", "import_version", "imported_at", "source_response_hash", "games_played", "games_started"}
    return any(value is not None and value > 0 for key, value in summary.items() if key not in ignored)


def _role_label(depth_order: int | None, role_status: str | None) -> str:
    status = (_clean(role_status) or "").lower()
    if depth_order == 1 or status in {"starter", "starting"}:
        return "projected starter"
    if depth_order == 2 or status in {"rotation", "contributor"}:
        return "projected contributor"
    if depth_order and depth_order >= 3:
        return "depth-chart option"
    return "role still being established"


def _production_label(history: dict[str, Any] | None) -> str:
    if not history:
        return "limited verified college production"
    points = _finite(history.get("fantasy_points"))
    games = _finite(history.get("games_played"))
    if points and games and games >= 8 and points / games >= 14:
        return "established fantasy production"
    if points and points > 0:
        return "returning college production"
    return "limited verified college production"


def _team_environment_label(percentile: float | None) -> str | None:
    if percentile is None:
        return None
    if percentile >= 0.75:
        return "one of the stronger projected team environments"
    if percentile >= 0.50:
        return "an above-median projected team environment"
    if percentile <= 0.25:
        return "a lower projected team environment"
    return "a middle-tier projected team environment"


def _position_projection_label(percentile: float | None) -> str | None:
    if percentile is None:
        return None
    if percentile >= 0.85:
        return "top-tier position projection"
    if percentile >= 0.65:
        return "above-average position projection"
    if percentile <= 0.30:
        return "lower-range position projection"
    return "middle-range position projection"


def build_player_season_outlook_facts(db: Session, player: Player, *, season_year: int) -> dict[str, Any]:
    """Build a complete local JSON evidence record before prose is rendered."""

    position = (_clean(player.position) or "").upper()
    context = db.query(PlayerSeasonContext).filter(
        PlayerSeasonContext.player_id == player.id, PlayerSeasonContext.season == season_year
    ).one_or_none()
    role_snapshot = db.query(PlayerRoleSnapshot).filter(
        PlayerRoleSnapshot.player_id == player.id, PlayerRoleSnapshot.season == season_year
    ).order_by(PlayerRoleSnapshot.week.asc(), PlayerRoleSnapshot.updated_at.desc()).first()
    history_rows = db.query(PlayerHistoricalSeasonStat).filter(
        PlayerHistoricalSeasonStat.player_id == player.id,
        PlayerHistoricalSeasonStat.season < season_year,
        PlayerHistoricalSeasonStat.season_type == "regular",
        PlayerHistoricalSeasonStat.is_final.is_(True),
    ).order_by(PlayerHistoricalSeasonStat.season.desc(), PlayerHistoricalSeasonStat.imported_at.desc()).all()
    history = next((row for row in history_rows if _meaningful_history(row, position)), None)
    environment = db.query(TeamEnvironment).filter(
        TeamEnvironment.season == season_year, TeamEnvironment.team_name == player.school
    ).order_by(TeamEnvironment.week.asc(), TeamEnvironment.updated_at.desc()).first()
    environment_percentile: float | None = None
    if environment and _finite(environment.expected_points) is not None:
        all_points = [
            float(row.expected_points)
            for row in db.query(TeamEnvironment).filter(
                TeamEnvironment.season == season_year, TeamEnvironment.week == environment.week
            ).all()
            if _finite(row.expected_points) is not None
        ]
        if all_points:
            environment_percentile = sum(point <= float(environment.expected_points) for point in all_points) / len(all_points)

    depth_order = role_snapshot.depth_order if role_snapshot and role_snapshot.depth_order is not None else player.depth_order
    projection_total = _finite(player.sheet_projected_season_points)
    projection_stats = player.sheet_projection_stats if isinstance(player.sheet_projection_stats, dict) else {}
    position_projection_percentile: float | None = None
    if projection_total is not None:
        position_projection_values = [
            numeric for raw in db.query(Player.sheet_projected_season_points).filter(
                Player.position == position, Player.sheet_projected_season_points.isnot(None)
            ).all() if (numeric := _finite(raw[0])) is not None
        ]
        if position_projection_values:
            position_projection_percentile = sum(value <= projection_total for value in position_projection_values) / len(position_projection_values)
    role_status = role_snapshot.role_status if role_snapshot else None
    current_team = _clean(player.school)
    return {
        "facts_version": PLAYER_OUTLOOK_FACTS_VERSION,
        "player": {
            "id": player.id, "name": _clean(player.name), "position": position, "school": current_team,
            "class": _class_label(player), "position_rank": player.cfb27_position_rank,
        },
        "historical": _history_summary(history, position),
        "projection": {
            "season_year": season_year, "projected_points": projection_total,
            "position_projection_percentile": position_projection_percentile, "stats": projection_stats,
            "source_sheet_id": _clean(player.sheet_source_sheet_id),
            "synced_at": player.sheet_synced_at.isoformat() if player.sheet_synced_at else None,
        },
        "role": {
            "depth_order": depth_order, "role_status": _clean(role_status),
            "source": role_snapshot.source if role_snapshot else (context.identity_source if context else "player.depth_order"),
            "confidence": _finite(context.role_confidence) if context else None,
        },
        "team_context": {
            "current_team": current_team, "historical_team": _clean(context.historical_team_name) if context else None,
            "is_transfer": bool(context.is_transfer) if context else False, "environment_week": environment.week if environment else None,
            "expected_points_percentile": environment_percentile,
        },
        "derived": {
            "experience_status": _class_label(player), "projected_role": _role_label(depth_order, role_status),
            "production_profile": _production_label(_history_summary(history, position)),
            "position_projection_label": _position_projection_label(position_projection_percentile),
            "team_environment_label": _team_environment_label(environment_percentile),
        },
    }


def _history_clause(history: dict[str, Any] | None, position: str) -> str:
    if not history:
        return "Verified local records do not yet contain a final prior season with usable production totals."
    season, team = history["season"], history.get("team")
    team_suffix = f" at {team}" if team else ""
    if position == "QB" and history.get("passing_yards") is not None:
        return f"In {season}{team_suffix}, he recorded {round(history['passing_yards']):,} passing yards and {round(history.get('passing_touchdowns') or 0)} passing touchdowns."
    if position == "RB" and history.get("rushing_yards") is not None:
        return f"In {season}{team_suffix}, he recorded {round(history['rushing_yards']):,} rushing yards and {round(history.get('rushing_touchdowns') or 0)} rushing touchdowns."
    if position in {"WR", "TE"} and history.get("receiving_yards") is not None:
        return f"In {season}{team_suffix}, he posted {round(history.get('receptions') or 0)} catches for {round(history['receiving_yards']):,} receiving yards and {round(history.get('receiving_touchdowns') or 0)} touchdowns."
    if position == "K" and history.get("field_goals_made") is not None:
        return f"In {season}{team_suffix}, he made {round(history['field_goals_made'])} field goals and {round(history.get('extra_points_made') or 0)} extra points."
    return f"In {season}{team_suffix}, he supplied verified college production."


def _allowed_numeric_tokens(facts: dict[str, Any]) -> set[str]:
    tokens = {str(facts["projection"]["season_year"])}
    for value in (facts.get("historical") or {}).values():
        numeric = _finite(value)
        if numeric is not None:
            tokens.add(str(int(numeric)) if numeric.is_integer() else str(numeric))
            tokens.add(f"{numeric:,.0f}" if numeric.is_integer() else f"{numeric:g}")
    rank = facts["player"].get("position_rank")
    if isinstance(rank, int):
        tokens.add(str(rank))
    return tokens


def validate_player_season_outlook(facts: dict[str, Any], text: str | None) -> list[str]:
    if not text:
        return ["outlook text is required for ready outlooks"]
    errors: list[str] = []
    words = re.findall(r"\b[\w'-]+\b", text)
    if not 45 <= len(words) <= 100:
        errors.append("outlook must contain 45-100 words")
    # Player names can contain normal abbreviations such as "Jr.", "St.",
    # and initials. Those periods are not sentence boundaries. Count only
    # punctuation that ends a sentence, after stripping short abbreviations
    # when they precede another capitalized name token.
    sentence_text = re.sub(r"\b(?:Jr|Sr|II|III|IV)\.(?=\s)", "", text)
    # A chained initial such as "A.J." has no whitespace after the first
    # period, so it must be removed as a complete token before the generic
    # short-abbreviation rule below.
    sentence_text = re.sub(r"\b(?:[A-Za-z]\.){2,}(?=\s)", "", sentence_text)
    sentence_text = re.sub(r"\b(?:[A-Za-z]{1,3})\.(?=\s+[A-Z])", "", sentence_text)
    if len(re.findall(r"[.!?](?=\s|$)", sentence_text)) not in {2, 3}:
        errors.append("outlook must contain two or three sentences")
    allowed_tokens = _allowed_numeric_tokens(facts)
    for token in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        if token not in allowed_tokens:
            errors.append(f"unverified numeric value in prose: {token}")
    return errors


def generate_player_season_outlook(facts: dict[str, Any]) -> GeneratedOutlook:
    player, projection = facts["player"], facts["projection"]
    if player.get("position") not in SUPPORTED_POSITIONS or not player.get("name") or not player.get("school") or projection.get("projected_points") is None:
        return GeneratedOutlook(facts=facts, text=None, status=INSUFFICIENT_DATA, validation_errors=[])
    derived, team_context = facts["derived"], facts["team_context"]
    transfer = " after a transfer" if team_context.get("is_transfer") else ""
    rank = player.get("position_rank")
    rank_clause = f" and a current #{rank} position rank" if isinstance(rank, int) and rank > 0 else ""
    environment = derived.get("team_environment_label")
    environment_clause = f" while {player['school']} is modeled as {environment}" if environment else ""
    text = re.sub(
        r"\s+",
        " ",
        f"{player['name']} enters {projection['season_year']} at {player['school']} as a {derived['experience_status']} {player['position']} and {derived['projected_role']}{transfer}. "
        f"{_history_clause(facts.get('historical'), player['position'])} The local preseason model combines {derived['production_profile']}, "
        f"{derived.get('position_projection_label') or 'a current position projection'}{rank_clause}, and this role{environment_clause}, giving fantasy managers a role-based outlook rather than an unsupported promise.",
    ).strip()
    errors = validate_player_season_outlook(facts, text)
    return GeneratedOutlook(facts=facts, text=text if not errors else None, status=READY if not errors else FAILED_VALIDATION, validation_errors=errors)


def persist_player_season_outlook(db: Session, *, player_id: int, season_year: int, generated: GeneratedOutlook, generator_version: str = PLAYER_OUTLOOK_GENERATOR_VERSION) -> PlayerSeasonOutlook:
    row = db.query(PlayerSeasonOutlook).filter(
        PlayerSeasonOutlook.player_id == player_id, PlayerSeasonOutlook.season_year == season_year,
        PlayerSeasonOutlook.outlook_type == PRESEASON_OUTLOOK_TYPE, PlayerSeasonOutlook.generator_version == generator_version,
    ).one_or_none()
    values = {
        "facts_version": PLAYER_OUTLOOK_FACTS_VERSION, "facts_json": generated.facts, "outlook_text": generated.text,
        "outlook_status": generated.status, "projection_source_batch_id": generated.facts["projection"].get("source_sheet_id"),
        "identity_source_batch_id": generated.facts["role"].get("source"), "generated_at": datetime.now(timezone.utc),
        "review_status": "AUTO_APPROVED" if generated.status == READY else "NEEDS_REVIEW",
    }
    if row is None:
        row = PlayerSeasonOutlook(player_id=player_id, season_year=season_year, outlook_type=PRESEASON_OUTLOOK_TYPE, generator_version=generator_version, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def get_persisted_player_season_outlook(db: Session, *, player_id: int, season_year: int) -> PlayerSeasonOutlook | None:
    return db.query(PlayerSeasonOutlook).filter(
        PlayerSeasonOutlook.player_id == player_id, PlayerSeasonOutlook.season_year == season_year,
        PlayerSeasonOutlook.outlook_type == PRESEASON_OUTLOOK_TYPE,
        PlayerSeasonOutlook.generator_version == PLAYER_OUTLOOK_GENERATOR_VERSION,
        PlayerSeasonOutlook.outlook_status == READY,
    ).one_or_none()
