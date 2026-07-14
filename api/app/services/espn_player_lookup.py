from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.provider_identity import (
    ProviderIdentityConflict,
    upsert_player_provider_mapping,
)


POSITION_ALIASES = {
    "QUARTERBACK": "QB",
    "RUNNING BACK": "RB",
    "WIDE RECEIVER": "WR",
    "TIGHT END": "TE",
    "PLACE KICKER": "K",
    "KICKER": "K",
}


@dataclass(frozen=True)
class ResolvedESPNPlayer:
    provider_player_id: str
    profile_payload: dict[str, Any] | None = None


def normalize_espn_lookup_text(value: str | None) -> str:
    normalized = (value or "").lower().replace("&", "and")
    normalized = re.sub(r"\b(jr|jr\.|sr|sr\.|iii|ii|iv|v)\b", "", normalized)
    return re.sub(r"[^a-z0-9]+", "", normalized).strip()


def _profile_athlete(profile_payload: dict[str, Any] | None) -> dict[str, Any]:
    athlete = profile_payload.get("athlete") if isinstance(profile_payload, dict) else None
    return athlete if isinstance(athlete, dict) else {}


def _profile_team_names(profile_payload: dict[str, Any] | None) -> list[str]:
    athlete = _profile_athlete(profile_payload)
    team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
    names = [
        team.get("displayName"),
        team.get("shortDisplayName"),
        team.get("name"),
        team.get("location"),
        team.get("abbreviation"),
    ]
    return [str(name).strip() for name in names if name]


def _profile_position(profile_payload: dict[str, Any] | None) -> str | None:
    athlete = _profile_athlete(profile_payload)
    position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
    raw = position.get("abbreviation") or position.get("displayName") or position.get("name")
    if not raw:
        return None
    text = str(raw).strip().upper()
    return POSITION_ALIASES.get(text, text)


def _item_name_matches(item: dict[str, Any], player: Player) -> bool:
    player_name = normalize_espn_lookup_text(player.name)
    return any(
        normalize_espn_lookup_text(str(item.get(key))) == player_name
        for key in ("displayName", "name", "fullName")
        if item.get(key)
    )


def _item_is_college_football_player(item: dict[str, Any]) -> bool:
    return (
        str(item.get("type") or "").lower() == "player"
        and str(item.get("sport") or "").lower() == "football"
        and str(item.get("league") or "").lower() == "college-football"
    )


def _school_matches(profile_payload: dict[str, Any] | None, player: Player) -> bool:
    school = normalize_espn_lookup_text(player.school)
    if not school:
        return False
    for team_name in _profile_team_names(profile_payload):
        normalized_team = normalize_espn_lookup_text(team_name)
        if school == normalized_team or school in normalized_team or normalized_team in school:
            return True
    return False


def _position_matches(profile_payload: dict[str, Any] | None, player: Player) -> bool:
    profile_position = _profile_position(profile_payload)
    if not profile_position:
        return False
    return profile_position == (player.position or "").strip().upper()


def resolve_espn_player_by_name(
    db: Session,
    player: Player,
    *,
    client: ESPNClient | None = None,
) -> ResolvedESPNPlayer | None:
    if not player.name or not player.school or not player.position:
        return None

    espn_client = client or ESPNClient()
    candidates = [
        item
        for item in espn_client.search_players(player.name, limit=10)
        if _item_is_college_football_player(item) and _item_name_matches(item, player) and item.get("id")
    ]
    for candidate in candidates:
        provider_player_id = str(candidate["id"]).strip()
        if not provider_player_id:
            continue
        profile_payload = espn_client.get_athlete_profile(provider_player_id)
        if not (_school_matches(profile_payload, player) and _position_matches(profile_payload, player)):
            continue
        try:
            upsert_player_provider_mapping(
                db,
                player_id=player.id,
                provider="espn",
                provider_player_id=provider_player_id,
                match_confidence=0.95,
                verification_status="legacy_backfill",
                reason="Exact ESPN player search match by name, school, and position.",
            )
            db.commit()
        except ProviderIdentityConflict:
            db.rollback()
            return None
        return ResolvedESPNPlayer(provider_player_id=provider_player_id, profile_payload=profile_payload)

    return None
