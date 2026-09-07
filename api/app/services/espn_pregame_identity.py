"""Bounded pregame ESPN identity reconciliation.

This work is deliberately separate from box-score promotion: an identity
lookup may be unavailable, but it must never prevent healthy live games from
scoring. Only an exact ESPN name, school, and position match is promoted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.espn_live_scoring import ESPN_PROVIDER
from collegefootballfantasy_api.app.services.espn_player_lookup import resolve_espn_player_identity_and_profile
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school


PREGAME_IDENTITY_HORIZON_HOURS = 36
PREGAME_IDENTITY_BATCH_SIZE = 2


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _school_key(value: str | None) -> str:
    return canonical_school_name(value or "") or normalize_school(value or "") or ""


def reconcile_pregame_espn_identities(
    db: Session,
    *,
    season: int,
    week: int,
    client: ESPNClient,
    now: datetime | None = None,
    limit: int = PREGAME_IDENTITY_BATCH_SIZE,
) -> dict[str, int]:
    """Verify a tiny set of upcoming active-roster identities without scoring.

    Existing verified mappings are never overwritten. Candidates are ordered
    with active roster players first, then by canonical player id. A failed or
    ambiguous lookup is reported to the caller but leaves live scoring alone.
    """

    current = _utc(now or datetime.now(timezone.utc))
    window_end = current + timedelta(hours=PREGAME_IDENTITY_HORIZON_HOURS)
    schools = {
        _school_key(row.team_name)
        for row in db.query(TeamSchedule)
        .filter(
            TeamSchedule.season == season,
            TeamSchedule.week == week,
            TeamSchedule.is_bye.is_(False),
            TeamSchedule.kickoff_at > current,
            TeamSchedule.kickoff_at <= window_end,
        )
        .all()
        if _school_key(row.team_name)
    }
    if not schools or limit < 1:
        return {"considered": 0, "verified": 0, "unresolved": 0}

    active_ids = {
        player_id
        for (player_id,) in db.query(RosterEntry.player_id)
        .join(League, League.id == RosterEntry.league_id)
        .filter(
            RosterEntry.status == "active",
            League.season_year == season,
            League.status.notin_(("cancelled", "archived")),
        )
        .distinct()
        .all()
    }
    mappings = {
        row.player_id: row
        for row in db.query(PlayerProviderId)
        .filter(PlayerProviderId.provider == ESPN_PROVIDER)
        .all()
    }
    candidates = [
        player
        for player in db.query(Player).order_by(Player.id.asc()).all()
        if _school_key(player.school) in schools
        and (player.id not in mappings or mappings[player.id].verification_status != "verified")
    ]
    candidates.sort(key=lambda player: (player.id not in active_ids, player.id))
    considered = verified = unresolved = 0
    for player in candidates[:limit]:
        considered += 1
        result = resolve_espn_player_identity_and_profile(db, player, client=client)
        mapping = mappings.get(player.id) or (
            db.query(PlayerProviderId)
            .filter_by(player_id=player.id, provider=ESPN_PROVIDER)
            .one_or_none()
        )
        if result.outcome == "matched" and mapping is not None:
            # The resolver has already required an exact player name, school,
            # and position match. Mark this pregame result as admissible by
            # the live-scoring readiness gate.
            mapping.verification_status = "verified"
            mapping.verified_at = current
            db.commit()
            verified += 1
        else:
            unresolved += 1
    return {"considered": considered, "verified": verified, "unresolved": unresolved}
