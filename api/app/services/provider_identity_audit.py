from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_player_identity_audit import ProviderPlayerIdentityAudit
from collegefootballfantasy_api.app.models.provider_unmatched_player_row import ProviderUnmatchedPlayerRow


def provider_player_id(row: dict[str, Any]) -> str | None:
    for key in ("ESPNPlayerID", "PlayerID", "PlayerId", "player_id", "playerId", "ExternalID", "external_id"):
        value = row.get(key)
        if value is not None and value != "":
            return str(value)
    return None


def provider_player_name(row: dict[str, Any]) -> str | None:
    for key in ("PlayerName", "Name", "name", "player_name"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def provider_team(row: dict[str, Any]) -> str | None:
    for key in ("School", "Team", "team", "TeamName", "team_name"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def record_unmatched_provider_row(
    db: Session,
    *,
    provider: str,
    season: int,
    week: int,
    row: dict[str, Any],
    reason: str,
) -> ProviderUnmatchedPlayerRow:
    unmatched = ProviderUnmatchedPlayerRow(
        provider=provider,
        season=season,
        week=week,
        provider_player_id=provider_player_id(row),
        provider_player_name=provider_player_name(row),
        provider_team=provider_team(row),
        reason=reason,
        raw_json=row,
    )
    db.add(unmatched)
    return unmatched


def record_provider_identity_audit(
    db: Session,
    *,
    provider: str,
    season: int,
    week: int,
    row: dict[str, Any],
    player_id: int | None,
    match_type: str,
    confidence: int,
) -> ProviderPlayerIdentityAudit:
    audit = ProviderPlayerIdentityAudit(
        provider=provider,
        season=season,
        week=week,
        player_id=player_id,
        provider_player_id=provider_player_id(row),
        provider_player_name=provider_player_name(row),
        provider_team=provider_team(row),
        match_type=match_type,
        confidence=confidence,
        raw_json=row,
    )
    db.add(audit)
    return audit


def players_missing_provider_ids(db: Session) -> list[dict[str, Any]]:
    players = db.query(Player).order_by(Player.school.asc(), Player.name.asc()).all()
    rows: list[dict[str, Any]] = []
    for player in players:
        external_id = player.external_id or ""
        missing_espn_id = not external_id.startswith("espn:")
        missing_sportsdata_id = not external_id or external_id.startswith("espn:")
        if not missing_espn_id and not missing_sportsdata_id:
            continue
        rows.append(
            {
                "player_id": player.id,
                "name": player.name,
                "school": player.school,
                "position": player.position,
                "missing_espn_id": missing_espn_id,
                "missing_sportsdata_id": missing_sportsdata_id,
                "external_id": player.external_id,
            }
        )
    return rows


def duplicate_name_school_pairs(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(Player.name, Player.school, func.count(Player.id))
        .group_by(Player.name, Player.school)
        .having(func.count(Player.id) > 1)
        .all()
    )
    return [
        {
            "name": name,
            "school": school,
            "count": count,
        }
        for name, school, count in rows
    ]
