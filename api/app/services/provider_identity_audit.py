from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_provider_id import PlayerProviderId
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


def unmatched_row_dedupe_hash(
    *,
    provider: str,
    season: int,
    week: int,
    provider_player_id_value: str | None,
    provider_player_name_value: str | None,
    provider_team_value: str | None,
    reason: str,
) -> str:
    parts = [
        normalized_provider(provider),
        str(season),
        str(week),
        str(provider_player_id_value or "").strip().lower(),
        str(provider_player_name_value or "").strip().lower(),
        str(provider_team_value or "").strip().lower(),
        str(reason or "").strip().lower(),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def record_unmatched_provider_row(
    db: Session,
    *,
    provider: str,
    season: int,
    week: int,
    row: dict[str, Any],
    reason: str,
) -> ProviderUnmatchedPlayerRow:
    provider_player_id_value = provider_player_id(row)
    provider_player_name_value = provider_player_name(row)
    provider_team_value = provider_team(row)
    dedupe_hash = unmatched_row_dedupe_hash(
        provider=provider,
        season=season,
        week=week,
        provider_player_id_value=provider_player_id_value,
        provider_player_name_value=provider_player_name_value,
        provider_team_value=provider_team_value,
        reason=reason,
    )
    existing = db.query(ProviderUnmatchedPlayerRow).filter_by(dedupe_hash=dedupe_hash).first()
    if existing:
        existing.raw_json = row
        existing.reason = reason
        return existing
    unmatched = ProviderUnmatchedPlayerRow(
        provider=normalized_provider(provider),
        season=season,
        week=week,
        provider_player_id=provider_player_id_value,
        provider_player_name=provider_player_name_value,
        provider_team=provider_team_value,
        reason=reason,
        dedupe_hash=dedupe_hash,
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


def normalized_provider(provider: str) -> str:
    return provider.strip().lower()


def legacy_provider_external_id(player: Player, provider: str) -> str | None:
    external_id = str(player.external_id or "").strip()
    if not external_id:
        return None
    provider_key = normalized_provider(provider)
    prefixed = f"{provider_key}:"
    if external_id.lower().startswith(prefixed):
        return external_id.split(":", 1)[1].strip() or None
    if provider_key == "sportsdata" and ":" not in external_id:
        return external_id
    return None


def provider_id_for_player(player: Player, provider: str) -> str | None:
    provider_key = normalized_provider(provider)
    for provider_identity in getattr(player, "provider_ids", []) or []:
        if normalized_provider(provider_identity.provider) == provider_key:
            return provider_identity.provider_player_id
    return legacy_provider_external_id(player, provider_key)


def provider_player_index(db: Session, provider: str) -> dict[str, Player]:
    provider_key = normalized_provider(provider)
    rows = (
        db.query(PlayerProviderId.provider_player_id, Player)
        .join(Player, Player.id == PlayerProviderId.player_id)
        .filter(PlayerProviderId.provider == provider_key)
        .all()
    )
    index = {str(provider_player_id): player for provider_player_id, player in rows}
    for player in db.query(Player).filter(Player.external_id.isnot(None)).all():
        legacy_id = legacy_provider_external_id(player, provider_key)
        if legacy_id and legacy_id not in index:
            index[legacy_id] = player
        if legacy_id and provider_key == "espn" and f"espn:{legacy_id}" not in index:
            index[f"espn:{legacy_id}"] = player
    return index


def upsert_player_provider_id(
    db: Session,
    *,
    player_id: int,
    provider: str,
    provider_player_id: str,
    provider_team_id: str | None = None,
    match_confidence: int = 100,
    verified_at=None,
    verified_by_user_id: int | None = None,
) -> PlayerProviderId:
    provider_key = normalized_provider(provider)
    provider_player_key = str(provider_player_id).strip()
    identity = (
        db.query(PlayerProviderId)
        .filter(
            PlayerProviderId.provider == provider_key,
            PlayerProviderId.provider_player_id == provider_player_key,
        )
        .first()
    )
    if identity and identity.player_id != player_id:
        raise ValueError("provider player id is already linked to another player")
    if not identity:
        identity = (
            db.query(PlayerProviderId)
            .filter(PlayerProviderId.player_id == player_id, PlayerProviderId.provider == provider_key)
            .first()
        )
    if not identity:
        identity = PlayerProviderId(
            player_id=player_id,
            provider=provider_key,
            provider_player_id=provider_player_key,
        )
        db.add(identity)
    identity.provider_player_id = provider_player_key
    identity.provider_team_id = provider_team_id
    identity.match_confidence = max(0, min(int(match_confidence), 100))
    identity.verified_at = verified_at
    identity.verified_by_user_id = verified_by_user_id
    return identity


def map_unmatched_provider_row(
    db: Session,
    *,
    unmatched: ProviderUnmatchedPlayerRow,
    player_id: int,
    resolved_by_user_id: int,
    match_confidence: int = 100,
) -> ProviderUnmatchedPlayerRow:
    player = db.get(Player, player_id)
    if not player:
        raise ValueError("player not found")
    if not unmatched.provider_player_id:
        raise ValueError("unmatched provider row has no provider player id to map")
    resolved_at = datetime.now(timezone.utc)
    upsert_player_provider_id(
        db,
        player_id=player.id,
        provider=unmatched.provider,
        provider_player_id=unmatched.provider_player_id,
        provider_team_id=unmatched.provider_team,
        match_confidence=match_confidence,
        verified_at=resolved_at,
        verified_by_user_id=resolved_by_user_id,
    )
    unmatched.status = "mapped"
    unmatched.mapped_player_id = player.id
    unmatched.resolved_by_user_id = resolved_by_user_id
    unmatched.resolved_at = resolved_at
    return unmatched


def ignore_unmatched_provider_row(
    db: Session,
    *,
    unmatched: ProviderUnmatchedPlayerRow,
    resolved_by_user_id: int,
) -> ProviderUnmatchedPlayerRow:
    unmatched.status = "ignored"
    unmatched.resolved_by_user_id = resolved_by_user_id
    unmatched.resolved_at = datetime.now(timezone.utc)
    return unmatched


def resolve_unmatched_provider_row(
    db: Session,
    *,
    unmatched: ProviderUnmatchedPlayerRow,
    resolved_by_user_id: int,
) -> ProviderUnmatchedPlayerRow:
    unmatched.status = "resolved"
    unmatched.resolved_by_user_id = resolved_by_user_id
    unmatched.resolved_at = datetime.now(timezone.utc)
    return unmatched


def players_missing_provider_ids(db: Session) -> list[dict[str, Any]]:
    players = db.query(Player).order_by(Player.school.asc(), Player.name.asc()).all()
    rows: list[dict[str, Any]] = []
    for player in players:
        missing_espn_id = provider_id_for_player(player, "espn") is None
        missing_sportsdata_id = provider_id_for_player(player, "sportsdata") is None
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
                "provider_ids": [
                    {
                        "provider": provider_identity.provider,
                        "provider_player_id": provider_identity.provider_player_id,
                        "provider_team_id": provider_identity.provider_team_id,
                        "match_confidence": provider_identity.match_confidence,
                        "verified_at": provider_identity.verified_at,
                        "verified_by_user_id": provider_identity.verified_by_user_id,
                    }
                    for provider_identity in player.provider_ids
                ],
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
