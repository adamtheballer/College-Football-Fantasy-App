from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass(frozen=True)
class ESPNIdentityResolution:
    outcome: str
    resolved: ResolvedESPNPlayer | None = None
    profile_updated: bool = False
    detail: str | None = None


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


def _profile_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _profile_birthplace(profile_payload: dict[str, Any] | None) -> str | None:
    athlete = _profile_athlete(profile_payload)
    birth_place = athlete.get("birthPlace")
    if isinstance(birth_place, dict):
        values = [
            _profile_text(birth_place.get("city")),
            _profile_text(birth_place.get("state")),
            _profile_text(birth_place.get("country")),
        ]
    elif isinstance(birth_place, str):
        return _profile_text(birth_place)
    else:
        values = [
            _profile_text(athlete.get("birthCity")),
            _profile_text(athlete.get("birthState")),
            _profile_text(athlete.get("birthCountry")),
        ]
    return ", ".join(value for value in values if value) or None


def persist_espn_player_profile(player: Player, profile_payload: dict[str, Any] | None) -> bool:
    athlete = _profile_athlete(profile_payload)
    if not athlete:
        return False
    status = athlete.get("status") if isinstance(athlete.get("status"), dict) else {}
    headshot = athlete.get("headshot") if isinstance(athlete.get("headshot"), dict) else {}
    values = {
        "espn_height": _profile_text(athlete.get("displayHeight")),
        "espn_weight": _profile_text(athlete.get("displayWeight")),
        "espn_birthplace": _profile_birthplace(profile_payload),
        "espn_status": _profile_text(status.get("name") or status.get("abbreviation")),
        "espn_jersey": _profile_text(athlete.get("jersey")),
        "espn_headshot_url": _profile_text(headshot.get("href")),
    }
    for attribute, value in values.items():
        if value is not None:
            setattr(player, attribute, value)
    if values["espn_headshot_url"] and not player.image_url:
        player.image_url = values["espn_headshot_url"]
    player.espn_profile_synced_at = datetime.now(timezone.utc)
    return True


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


def resolve_espn_player_identity_and_profile(
    db: Session,
    player: Player,
    *,
    client: ESPNClient | None = None,
) -> ESPNIdentityResolution:
    if not player.name or not player.school or not player.position:
        return ESPNIdentityResolution(outcome="not_found", detail="Player is missing name, school, or position.")

    espn_client = client or ESPNClient()
    candidates = [
        item
        for item in espn_client.search_players(player.name, limit=10)
        if _item_is_college_football_player(item) and _item_name_matches(item, player) and item.get("id")
    ]
    matches: list[ResolvedESPNPlayer] = []
    seen_provider_ids: set[str] = set()
    for candidate in candidates:
        provider_player_id = str(candidate["id"]).strip()
        if not provider_player_id or provider_player_id in seen_provider_ids:
            continue
        seen_provider_ids.add(provider_player_id)
        profile_payload = espn_client.get_athlete_profile(provider_player_id)
        if not (_school_matches(profile_payload, player) and _position_matches(profile_payload, player)):
            continue
        matches.append(ResolvedESPNPlayer(provider_player_id=provider_player_id, profile_payload=profile_payload))

    if not matches:
        return ESPNIdentityResolution(outcome="not_found")
    if len(matches) > 1:
        return ESPNIdentityResolution(outcome="ambiguous", detail="Multiple ESPN profiles matched the player identity.")

    resolved = matches[0]
    try:
        upsert_player_provider_mapping(
            db,
            player_id=player.id,
            provider="espn",
            provider_player_id=resolved.provider_player_id,
            match_confidence=0.95,
            verification_status="legacy_backfill",
            reason="Exact ESPN player search match by name, school, and position.",
        )
        profile_updated = persist_espn_player_profile(player, resolved.profile_payload)
        db.commit()
    except ProviderIdentityConflict:
        db.rollback()
        return ESPNIdentityResolution(outcome="ambiguous", detail="ESPN identity conflicts with an existing trusted mapping.")
    return ESPNIdentityResolution(outcome="matched", resolved=resolved, profile_updated=profile_updated)


def resolve_espn_player_by_name(
    db: Session,
    player: Player,
    *,
    client: ESPNClient | None = None,
) -> ResolvedESPNPlayer | None:
    resolution = resolve_espn_player_identity_and_profile(db, player, client=client)
    return resolution.resolved if resolution.outcome == "matched" else None
