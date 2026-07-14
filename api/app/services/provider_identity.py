from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.college_team import CollegeTeam
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import (
    PlayerProviderId,
    ProviderIdentityAudit,
    TeamProviderId,
    UnmatchedProviderRow,
)
from collegefootballfantasy_api.app.services.power4 import (
    conference_for_school,
    list_power4_teams,
    resolve_power4_school,
)

VERIFIED_MAPPING_STATUSES = {"verified", "legacy_backfill"}
UNMATCHED_STATUSES = {"open", "mapped", "ignored", "resolved"}


class ProviderIdentityConflict(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _provider(value: str) -> str:
    return value.strip().lower()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, sort_keys=True, default=str)
        return value
    except TypeError:
        return json.loads(json.dumps(value, sort_keys=True, default=str))


def provider_row_dedupe_hash(
    *,
    provider: str,
    feed: str,
    row: dict[str, Any],
    season: int | None = None,
    week: int | None = None,
) -> str:
    payload = {
        "provider": _provider(provider),
        "feed": feed,
        "season": season,
        "week": week,
        "provider_player_id": _text(row.get("ESPNPlayerID") or row.get("PlayerID") or row.get("PlayerId")),
        "provider_team_id": _text(row.get("TeamID") or row.get("TeamId") or row.get("Team")),
        "player_name": _text(row.get("PlayerName") or row.get("Name") or row.get("FullName")),
        "team_name": _text(row.get("School") or row.get("TeamName") or row.get("Team")),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit_identity_event(
    db: Session,
    *,
    entity_type: str,
    action: str,
    entity_id: int | None = None,
    provider: str | None = None,
    provider_player_id: str | None = None,
    provider_team_id: str | None = None,
    unmatched_row_id: int | None = None,
    actor_user_id: int | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    reason: str | None = None,
) -> ProviderIdentityAudit:
    audit = ProviderIdentityAudit(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        provider=_provider(provider) if provider else None,
        provider_player_id=provider_player_id,
        provider_team_id=provider_team_id,
        unmatched_row_id=unmatched_row_id,
        actor_user_id=actor_user_id,
        before_state=before_state,
        after_state=after_state,
        reason=reason,
    )
    db.add(audit)
    return audit


def ensure_college_team(db: Session, name: str) -> CollegeTeam | None:
    canonical_name = resolve_power4_school(name) or _text(name)
    if not canonical_name:
        return None
    team = db.scalar(select(CollegeTeam).where(CollegeTeam.name == canonical_name))
    if team:
        return team
    team = CollegeTeam(name=canonical_name, conference=conference_for_school(canonical_name))
    db.add(team)
    db.flush()
    return team


def seed_power4_college_teams(db: Session) -> int:
    created = 0
    for team_name in list_power4_teams():
        if not db.scalar(select(CollegeTeam).where(CollegeTeam.name == team_name)):
            db.add(CollegeTeam(name=team_name, conference=conference_for_school(team_name)))
            created += 1
    db.flush()
    return created


def find_player_by_provider_id(db: Session, provider: str, provider_player_id: str | None) -> Player | None:
    if not provider_player_id:
        return None
    mapping = db.scalar(
        select(PlayerProviderId)
        .where(
            PlayerProviderId.provider == _provider(provider),
            PlayerProviderId.provider_player_id == str(provider_player_id),
        )
        .order_by(PlayerProviderId.verification_status.desc(), PlayerProviderId.id.asc())
    )
    return mapping.player if mapping else None


def upsert_player_provider_mapping(
    db: Session,
    *,
    player_id: int,
    provider: str,
    provider_player_id: str,
    provider_team_id: str | None = None,
    match_confidence: float | None = None,
    verification_status: str = "unverified",
    actor_user_id: int | None = None,
    reason: str | None = None,
) -> PlayerProviderId:
    normalized_provider = _provider(provider)
    existing = db.scalar(
        select(PlayerProviderId).where(
            PlayerProviderId.provider == normalized_provider,
            PlayerProviderId.provider_player_id == str(provider_player_id),
        )
    )
    if existing and existing.player_id != player_id and existing.verification_status in VERIFIED_MAPPING_STATUSES:
        raise ProviderIdentityConflict("verified provider mapping cannot be silently reassigned")

    player_provider_mapping = db.scalar(
        select(PlayerProviderId).where(
            PlayerProviderId.player_id == player_id,
            PlayerProviderId.provider == normalized_provider,
        )
    )
    if (
        existing
        and existing.player_id != player_id
        and player_provider_mapping
        and player_provider_mapping.id != existing.id
        and player_provider_mapping.provider_player_id != str(provider_player_id)
    ):
        raise ProviderIdentityConflict("provider mapping is ambiguous and requires manual resolution")
    if player_provider_mapping and player_provider_mapping.provider_player_id != str(provider_player_id):
        if player_provider_mapping.verification_status in VERIFIED_MAPPING_STATUSES:
            raise ProviderIdentityConflict("verified player provider mapping cannot be silently changed")
        existing = player_provider_mapping

    before_state = None
    if existing:
        before_state = {
            "player_id": existing.player_id,
            "provider_player_id": existing.provider_player_id,
            "provider_team_id": existing.provider_team_id,
            "verification_status": existing.verification_status,
        }
        existing.player_id = player_id
        existing.provider_team_id = provider_team_id
        existing.match_confidence = match_confidence
        existing.verification_status = verification_status
        if verification_status == "verified":
            existing.verified_at = _now()
            existing.verified_by_user_id = actor_user_id
        mapping = existing
    else:
        mapping = PlayerProviderId(
            player_id=player_id,
            provider=normalized_provider,
            provider_player_id=str(provider_player_id),
            provider_team_id=provider_team_id,
            match_confidence=match_confidence,
            verification_status=verification_status,
            verified_at=_now() if verification_status == "verified" else None,
            verified_by_user_id=actor_user_id if verification_status == "verified" else None,
        )
        db.add(mapping)
        db.flush()

    audit_identity_event(
        db,
        entity_type="player_provider_id",
        entity_id=mapping.id,
        action="upsert",
        provider=normalized_provider,
        provider_player_id=str(provider_player_id),
        provider_team_id=provider_team_id,
        actor_user_id=actor_user_id,
        before_state=before_state,
        after_state={
            "player_id": mapping.player_id,
            "provider_player_id": mapping.provider_player_id,
            "provider_team_id": mapping.provider_team_id,
            "verification_status": mapping.verification_status,
        },
        reason=reason,
    )
    return mapping


def upsert_team_provider_mapping(
    db: Session,
    *,
    team_name: str,
    provider: str,
    provider_team_id: str,
    provider_team_name: str | None = None,
) -> TeamProviderId | None:
    team = ensure_college_team(db, team_name)
    if not team:
        return None
    normalized_provider = _provider(provider)
    mapping = db.scalar(
        select(TeamProviderId).where(
            TeamProviderId.provider == normalized_provider,
            TeamProviderId.provider_team_id == str(provider_team_id),
        )
    )
    if not mapping:
        mapping = db.scalar(
            select(TeamProviderId).where(
                TeamProviderId.provider == normalized_provider,
                TeamProviderId.team_id == team.id,
            )
        )
    if mapping:
        mapping.team_id = team.id
        mapping.provider_team_id = str(provider_team_id)
        mapping.provider_team_name = provider_team_name or mapping.provider_team_name
        return mapping
    mapping = TeamProviderId(
        team_id=team.id,
        provider=normalized_provider,
        provider_team_id=str(provider_team_id),
        provider_team_name=provider_team_name,
    )
    db.add(mapping)
    db.flush()
    return mapping


def record_unmatched_provider_row(
    db: Session,
    *,
    provider: str,
    feed: str,
    row: dict[str, Any],
    season: int | None = None,
    week: int | None = None,
    reason: str | None = None,
) -> UnmatchedProviderRow:
    normalized_provider = _provider(provider)
    dedupe_hash = provider_row_dedupe_hash(provider=normalized_provider, feed=feed, row=row, season=season, week=week)
    unmatched = db.scalar(
        select(UnmatchedProviderRow).where(
            UnmatchedProviderRow.provider == normalized_provider,
            UnmatchedProviderRow.feed == feed,
            UnmatchedProviderRow.dedupe_hash == dedupe_hash,
        )
    )
    now = _now()
    if unmatched:
        unmatched.occurrence_count += 1
        unmatched.last_seen_at = now
        if unmatched.status in {"resolved", "mapped"}:
            unmatched.status = "open"
            unmatched.resolved_at = None
            unmatched.resolved_by_user_id = None
        db.add(unmatched)
        return unmatched

    unmatched = UnmatchedProviderRow(
        provider=normalized_provider,
        feed=feed,
        season=season,
        week=week,
        provider_player_id=_text(row.get("ESPNPlayerID") or row.get("PlayerID") or row.get("PlayerId")),
        provider_team_id=_text(row.get("TeamID") or row.get("TeamId") or row.get("Team")),
        player_name=_text(row.get("PlayerName") or row.get("Name") or row.get("FullName")),
        team_name=_text(row.get("School") or row.get("TeamName") or row.get("Team")),
        dedupe_hash=dedupe_hash,
        raw_payload=_jsonable(row),
        status="open",
        occurrence_count=1,
        last_seen_at=now,
        notes=reason,
    )
    db.add(unmatched)
    db.flush()
    audit_identity_event(
        db,
        entity_type="unmatched_provider_row",
        entity_id=unmatched.id,
        action="record_open",
        provider=normalized_provider,
        provider_player_id=unmatched.provider_player_id,
        provider_team_id=unmatched.provider_team_id,
        unmatched_row_id=unmatched.id,
        after_state={"status": unmatched.status, "dedupe_hash": unmatched.dedupe_hash},
        reason=reason,
    )
    return unmatched


def map_unmatched_row_to_player(
    db: Session,
    *,
    unmatched_row_id: int,
    player_id: int,
    actor_user_id: int,
    match_confidence: float | None = 1.0,
    reason: str | None = None,
) -> UnmatchedProviderRow:
    unmatched = db.get(UnmatchedProviderRow, unmatched_row_id)
    if not unmatched:
        raise LookupError("unmatched provider row not found")
    player = db.get(Player, player_id)
    if not player:
        raise LookupError("player not found")
    provider_player_id = unmatched.provider_player_id
    if not provider_player_id:
        raise ValueError("unmatched row has no provider player id")

    before_state = {"status": unmatched.status, "mapped_player_id": unmatched.mapped_player_id}
    upsert_player_provider_mapping(
        db,
        player_id=player.id,
        provider=unmatched.provider,
        provider_player_id=provider_player_id,
        provider_team_id=unmatched.provider_team_id,
        match_confidence=match_confidence,
        verification_status="verified",
        actor_user_id=actor_user_id,
        reason=reason,
    )
    unmatched.status = "mapped"
    unmatched.mapped_player_id = player.id
    unmatched.resolved_by_user_id = actor_user_id
    unmatched.resolved_at = _now()
    unmatched.notes = reason
    db.add(unmatched)
    audit_identity_event(
        db,
        entity_type="unmatched_provider_row",
        entity_id=unmatched.id,
        action="map_to_player",
        provider=unmatched.provider,
        provider_player_id=provider_player_id,
        provider_team_id=unmatched.provider_team_id,
        unmatched_row_id=unmatched.id,
        actor_user_id=actor_user_id,
        before_state=before_state,
        after_state={"status": unmatched.status, "mapped_player_id": unmatched.mapped_player_id},
        reason=reason,
    )
    return unmatched


def mark_unmatched_row_status(
    db: Session,
    *,
    unmatched_row_id: int,
    status: str,
    actor_user_id: int,
    reason: str | None = None,
) -> UnmatchedProviderRow:
    if status not in UNMATCHED_STATUSES:
        raise ValueError("invalid unmatched row status")
    unmatched = db.get(UnmatchedProviderRow, unmatched_row_id)
    if not unmatched:
        raise LookupError("unmatched provider row not found")
    before_state = {"status": unmatched.status, "mapped_player_id": unmatched.mapped_player_id}
    unmatched.status = status
    unmatched.notes = reason
    if status in {"ignored", "resolved"}:
        unmatched.resolved_by_user_id = actor_user_id
        unmatched.resolved_at = _now()
    elif status == "open":
        unmatched.resolved_by_user_id = None
        unmatched.resolved_at = None
        unmatched.mapped_player_id = None
    db.add(unmatched)
    audit_identity_event(
        db,
        entity_type="unmatched_provider_row",
        entity_id=unmatched.id,
        action=f"mark_{status}",
        provider=unmatched.provider,
        provider_player_id=unmatched.provider_player_id,
        provider_team_id=unmatched.provider_team_id,
        unmatched_row_id=unmatched.id,
        actor_user_id=actor_user_id,
        before_state=before_state,
        after_state={"status": unmatched.status, "mapped_player_id": unmatched.mapped_player_id},
        reason=reason,
    )
    return unmatched


def provider_identity_readiness(
    db: Session,
    *,
    provider: str,
    season: int,
    week: int,
) -> dict[str, Any]:
    seed_power4_college_teams(db)
    normalized_provider = _provider(provider)
    total_players = db.scalar(select(func.count(Player.id))) or 0
    mapped_players = (
        db.scalar(
            select(func.count(PlayerProviderId.id)).where(
                PlayerProviderId.provider == normalized_provider,
                PlayerProviderId.verification_status.in_(VERIFIED_MAPPING_STATUSES),
            )
        )
        or 0
    )
    total_college_teams = db.scalar(select(func.count(CollegeTeam.id))) or 0
    mapped_college_teams = (
        db.scalar(select(func.count(TeamProviderId.id)).where(TeamProviderId.provider == normalized_provider)) or 0
    )
    open_unmatched = (
        db.scalar(
            select(func.count(UnmatchedProviderRow.id)).where(
                UnmatchedProviderRow.provider == normalized_provider,
                UnmatchedProviderRow.status == "open",
            )
        )
        or 0
    )

    player_schools = {school for (school,) in db.execute(select(Player.school).distinct()).all() if school}
    missing_team_mappings: list[str] = []
    missing_schedule: list[str] = []
    missing_kickoff: list[str] = []
    bye_teams: list[str] = []
    for school in sorted(player_schools):
        canonical_school = resolve_power4_school(school)
        if not canonical_school:
            missing_team_mappings.append(school)
            continue
        college_team = ensure_college_team(db, canonical_school)
        if not college_team:
            missing_team_mappings.append(school)
            continue
        team_mapping = db.scalar(
            select(TeamProviderId).where(
                TeamProviderId.provider == normalized_provider,
                TeamProviderId.team_id == college_team.id,
            )
        )
        if not team_mapping:
            missing_team_mappings.append(canonical_school)
        games = db.execute(
            select(Game).where(
                Game.season == season,
                Game.week == week,
                Game.season_type == "regular",
                ((Game.home_team == canonical_school) | (Game.away_team == canonical_school)),
            )
        ).scalars().all()
        if not games:
            bye_teams.append(canonical_school)
            continue
        if all(game.start_date is None for game in games):
            missing_kickoff.append(canonical_school)
        if not games:
            missing_schedule.append(canonical_school)

    return {
        "provider": normalized_provider,
        "season": season,
        "week": week,
        "players_total": total_players,
        "players_verified_mapped": mapped_players,
        "college_teams_total": total_college_teams,
        "college_teams_mapped": mapped_college_teams,
        "open_unmatched_rows": open_unmatched,
        "missing_team_mappings": sorted(set(missing_team_mappings)),
        "missing_schedule_teams": sorted(set(missing_schedule)),
        "missing_kickoff_teams": sorted(set(missing_kickoff)),
        "bye_teams": sorted(set(bye_teams)),
        "ready": open_unmatched == 0 and not missing_team_mappings and not missing_kickoff,
    }
