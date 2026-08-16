"""Fail-closed readiness and operations reporting for ESPN live scoring.

This module is deliberately read-only.  It is used both by the admin health
endpoint and by the authoritative promotion boundary in the scoring worker.
That keeps a configuration typo from turning an unresolved active starter into
an authoritative zero-point score.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.scoring_rules import (
    LEGACY_BETA_KICKER_RULES,
    ScoringRulesValidationError,
    validate_scoring_rules,
)
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll, ProviderGameSnapshot
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId, UnmatchedProviderRow
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.worker_heartbeat import WorkerHeartbeat
from collegefootballfantasy_api.app.services.espn_live_scoring import ESPN_PROVIDER, MIN_GAME_POLL_INTERVAL_SECONDS, espn_week_freshness
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school


WORKER_NAME = "espn_scoring_processor"
WORKER_STALE_SECONDS = 120
UNAVAILABLE_SCHEDULE_STATUSES = {"tbd", "postponed", "cancelled", "canceled"}


class PublicScoringPreflightError(RuntimeError):
    """Promotion was refused before any public scoring table could be changed."""

    def __init__(self, reason_codes: list[str]) -> None:
        self.reason_codes = reason_codes
        super().__init__("public live-scoring preflight failed: " + ", ".join(reason_codes))


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_verified_mapping(mapping: PlayerProviderId | None) -> bool:
    return bool(mapping and mapping.verification_status == "verified" and str(mapping.provider_player_id or "").isdigit())


def ensure_official_acquisition_identity(db: Session, *, league: League, player: Player) -> None:
    """Keep unresolved players searchable while preventing official score risk."""

    if not settings.live_scoring_identity_guard_enabled:
        return
    if (league.platform or "").lower() in {"mock", "practice", "non_authoritative"}:
        return
    mapping = (
        db.query(PlayerProviderId)
        .filter(PlayerProviderId.player_id == player.id, PlayerProviderId.provider == ESPN_PROVIDER)
        .one_or_none()
    )
    if not _is_verified_mapping(mapping):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live scoring identity pending; this player cannot be added to an official league until ESPN identity verification completes.",
        )


def unresolved_active_starters(db: Session, *, season: int, week: int) -> list[dict[str, Any]]:
    """Return only non-PII details for starters lacking verified ESPN identity."""

    rows = (
        db.query(LineupWeekSnapshot, Player, League, PlayerProviderId)
        .join(Player, Player.id == LineupWeekSnapshot.player_id)
        .join(League, League.id == LineupWeekSnapshot.league_id)
        .outerjoin(
            PlayerProviderId,
            (PlayerProviderId.player_id == Player.id) & (PlayerProviderId.provider == ESPN_PROVIDER),
        )
        .filter(
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
            LineupWeekSnapshot.is_starter.is_(True),
            League.status.notin_(("cancelled", "archived")),
        )
        .all()
    )
    unresolved: list[dict[str, Any]] = []
    for snapshot, player, league, mapping in rows:
        if _is_verified_mapping(mapping):
            continue
        unresolved.append(
            {
                "player_id": player.id,
                "name": player.name,
                "school": player.school,
                "position": player.position,
                "league_id": league.id,
                "week": snapshot.week,
                "slot": snapshot.slot,
                "reason": "UNRESOLVED_STARTER_ESPN_ID",
            }
        )
    return unresolved


def _school_key(value: str | None) -> str:
    return canonical_school_name(value or "") or normalize_school(value or "") or ""


def _schedule_reason_codes(db: Session, *, season: int, week: int) -> list[str]:
    """Check only active-roster schedule authority, never legacy sheet rows."""

    active_schools = {
        _school_key(school)
        for (school,) in (
            db.query(Player.school)
            .join(RosterEntry, RosterEntry.player_id == Player.id)
            .join(League, League.id == RosterEntry.league_id)
            .filter(RosterEntry.status == "active", League.season_year == season, League.status.notin_(("cancelled", "archived")))
            .distinct()
            .all()
        )
        if _school_key(school)
    }
    # No active roster can be affected by a public promotion.  The worker
    # likewise discovers no relevant provider games in this state.
    if not active_schools:
        return []
    schedules = [
        row
        for row in db.query(TeamSchedule).filter(TeamSchedule.season == season, TeamSchedule.week == week).all()
        if _school_key(row.team_name) in active_schools
    ]
    for row in schedules:
        if row.is_bye:
            continue
        game = db.get(Game, row.game_id) if row.game_id is not None else None
        if game is None or not str(game.external_id or "").isdigit() or row.kickoff_at is None:
            return ["UNVERIFIED_ESPN_GAME_ID"]
        if (game.schedule_status or "").lower() in UNAVAILABLE_SCHEDULE_STATUSES:
            return ["UNAVAILABLE_ESPN_GAME"]
    return []


def _unsupported_league_ids(db: Session, *, season: int) -> list[int]:
    invalid: list[int] = []
    rows = (
        db.query(League.id, LeagueSettings.scoring_json)
        .outerjoin(LeagueSettings, LeagueSettings.league_id == League.id)
        .filter(League.season_year == season, League.status.notin_(("cancelled", "archived")))
        .all()
    )
    for league_id, scoring_json in rows:
        try:
            validate_scoring_rules(scoring_json or {})
        except ScoringRulesValidationError:
            invalid.append(league_id)
    return invalid


def public_scoring_preflight(db: Session, *, season: int, week: int, now: datetime | None = None) -> dict[str, Any]:
    """Read-only, machine-readable authority gate for ``SCORING_MODE=enabled``."""

    current = _utc(now) or _now()
    reason_codes: list[str] = []
    heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_name == WORKER_NAME).one_or_none()
    heartbeat_at = _utc(heartbeat.heartbeat_at) if heartbeat else None
    heartbeat_age = int((current - heartbeat_at).total_seconds()) if heartbeat_at else None
    if heartbeat is None or heartbeat.status != "healthy" or heartbeat_age is None or heartbeat_age > WORKER_STALE_SECONDS:
        reason_codes.append("SCORING_WORKER_UNHEALTHY")
    reason_codes.extend(_schedule_reason_codes(db, season=season, week=week))
    starters = unresolved_active_starters(db, season=season, week=week)
    if starters:
        reason_codes.append("UNRESOLVED_STARTER_ESPN_ID")
    unsupported = _unsupported_league_ids(db, season=season)
    if unsupported:
        reason_codes.append("UNSUPPORTED_LEAGUE_SCORING")
    blocked = (
        db.query(ProviderGamePoll)
        .filter(
            ProviderGamePoll.provider == ESPN_PROVIDER,
            ProviderGamePoll.season == season,
            ProviderGamePoll.week == week,
            ProviderGamePoll.status == "blocked",
        )
        .count()
    )
    if blocked:
        reason_codes.append("PROVIDER_OUTAGE_OR_BLOCKED")
    return {
        "ready": not reason_codes,
        "reason_codes": reason_codes,
        "season": season,
        "week": week,
        "worker": {"name": WORKER_NAME, "status": heartbeat.status if heartbeat else "missing", "heartbeat_age_seconds": heartbeat_age},
        "unresolved_starters": starters,
        "unsupported_league_ids": unsupported,
        "blocked_provider_games": blocked,
    }


def assert_public_scoring_ready(db: Session, *, season: int, week: int, now: datetime | None = None) -> None:
    report = public_scoring_preflight(db, season=season, week=week, now=now)
    if not report["ready"]:
        raise PublicScoringPreflightError(report["reason_codes"])


def _minimum_success_interval_seconds(snapshots: list[ProviderGameSnapshot]) -> int | None:
    grouped: dict[str, list[datetime]] = defaultdict(list)
    for snapshot in snapshots:
        # Receipt time validates the worker's 180-second request cadence.  It
        # is deliberately separate from provider ordering, which only trusts
        # explicit ESPN revisions or game-progress markers.
        at = _utc(snapshot.captured_at) or _utc(snapshot.provider_as_of)
        if at is not None:
            grouped[snapshot.provider_game_id].append(at)
    intervals = [int((right - left).total_seconds()) for values in grouped.values() for left, right in zip(sorted(values), sorted(values)[1:])]
    return min(intervals) if intervals else None


def scoring_operations_report(db: Session, *, season: int, week: int, now: datetime | None = None) -> dict[str, Any]:
    """Server-side, secret-free operations view for one scoring week."""

    current = _utc(now) or _now()
    polls = (
        db.query(ProviderGamePoll)
        .filter(ProviderGamePoll.provider == ESPN_PROVIDER, ProviderGamePoll.season == season, ProviderGamePoll.week == week)
        .all()
    )
    game_polls = [row for row in polls if not row.provider_game_id.startswith("discovery:")]
    snapshots = (
        db.query(ProviderGameSnapshot)
        .filter(ProviderGameSnapshot.provider == ESPN_PROVIDER, ProviderGameSnapshot.season == season, ProviderGameSnapshot.week == week)
        .all()
    )
    heartbeat = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_name == WORKER_NAME).one_or_none()
    heartbeat_at = _utc(heartbeat.heartbeat_at) if heartbeat else None
    heartbeat_age = int((current - heartbeat_at).total_seconds()) if heartbeat_at else None
    last_poll = max((_utc(row.last_success_at) for row in game_polls if row.last_success_at), default=None)
    next_poll = min((_utc(row.next_poll_at) for row in game_polls if row.next_poll_at), default=None)
    errors = [str(row.error_message or "") for row in game_polls]
    unmatched = (
        db.query(func.count(UnmatchedProviderRow.id))
        .filter(UnmatchedProviderRow.provider == ESPN_PROVIDER, UnmatchedProviderRow.season == season, UnmatchedProviderRow.week == week, UnmatchedProviderRow.status == "open")
        .scalar()
        or 0
    )
    freshness = espn_week_freshness(db, season=season, week=week, now=current)
    active = [row for row in game_polls if row.status == "live"]
    alerts: list[dict[str, str]] = []
    if active and (heartbeat_age is None or heartbeat_age > WORKER_STALE_SECONDS):
        alerts.append({"severity": "critical", "code": "SCORING_WORKER_HEARTBEAT_STALE"})
    if any(row.status == "blocked" for row in game_polls):
        alerts.append({"severity": "critical", "code": "PROVIDER_BLOCKED_403"})
    if any(row.failure_count >= 3 for row in game_polls):
        alerts.append({"severity": "error", "code": "REPEATED_GAME_POLL_FAILURE"})
    if any("429" in error for error in errors):
        alerts.append({"severity": "warning", "code": "ESPN_RATE_LIMIT_429"})
    if any("403" in error for error in errors):
        alerts.append({"severity": "warning", "code": "ESPN_FORBIDDEN_403"})
    if any("timeout" in error.lower() for error in errors):
        alerts.append({"severity": "warning", "code": "ESPN_TIMEOUT"})
    if freshness.state in {"delayed", "stale"}:
        alerts.append({"severity": "warning", "code": f"PROVIDER_DATA_{freshness.state.upper()}"})
    if unmatched:
        alerts.append({"severity": "warning", "code": "UNMATCHED_LIVE_PLAYER_ROWS"})
    stale_rejections = sum(row.stale_snapshot_count for row in game_polls)
    ambiguous_quarantines = sum(row.ambiguous_snapshot_count for row in game_polls)
    pending_final_corrections = sum(row.pending_final_correction_count for row in game_polls)
    # A single rejected response can be normal CDN/provider behavior.  Repeated
    # unresolved ordering evidence needs an operator without noisy live alerts.
    if stale_rejections >= 3:
        alerts.append({"severity": "warning", "code": "REPEATED_STALE_PROVIDER_SNAPSHOTS"})
    if ambiguous_quarantines >= 3:
        alerts.append({"severity": "warning", "code": "REPEATED_AMBIGUOUS_PROVIDER_SNAPSHOTS"})
    if pending_final_corrections:
        alerts.append({"severity": "error", "code": "PENDING_FINAL_CORRECTION_REVIEW"})
    return {
        "season": season,
        "week": week,
        "worker": {"name": WORKER_NAME, "status": heartbeat.status if heartbeat else "missing", "heartbeat_age_seconds": heartbeat_age, "details": heartbeat.details_json if heartbeat else {}},
        "game_polling": {
            "due_games": sum(1 for row in game_polls if row.next_poll_at and _utc(row.next_poll_at) <= current),
            "active_games": len(active),
            "last_successful_poll_at": last_poll,
            "next_poll_at": next_poll,
            "minimum_success_interval_seconds": _minimum_success_interval_seconds(snapshots),
            "minimum_required_interval_seconds": MIN_GAME_POLL_INTERVAL_SECONDS,
            "http_403_count": sum("403" in error for error in errors),
            "http_429_count": sum("429" in error for error in errors),
            "timeout_count": sum("timeout" in error.lower() for error in errors),
            "provider_failure_count": sum(row.failure_count for row in game_polls),
            "accepted_snapshot_count": sum(row.accepted_snapshot_count for row in game_polls),
            "duplicate_snapshot_count": sum(row.duplicate_snapshot_count for row in game_polls),
            "stale_snapshot_rejection_count": stale_rejections,
            "ambiguous_snapshot_quarantine_count": ambiguous_quarantines,
            "pending_final_correction_count": pending_final_corrections,
        },
        "identity": {"open_unmatched_live_rows": unmatched},
        "freshness": {"state": freshness.state, "data_age_seconds": freshness.data_age_seconds, "relevant_game_count": freshness.relevant_game_count},
        "shadow": {"candidate_snapshots": len(snapshots), "public_promotions": 0},
        "alerts": alerts,
        "preflight": public_scoring_preflight(db, season=season, week=week, now=current),
    }


def flat_field_goal_league_audit(db: Session, *, season: int) -> dict[str, Any]:
    """Read-only classification; historical league rules are never changed here."""

    def provenance(settings: LeagueSettings | None) -> tuple[str, str]:
        """Classify only when the stored beta lock proves the source.

        JSON values alone cannot tell a deliberate flat-three selection from
        the former beta default.  The creation-time immutable snapshot is the
        proof.  Anything without it intentionally remains unknown instead of
        being silently treated as a product default.
        """

        snapshot = (settings.scoring_snapshot_json if settings else None) or {}
        raw = (settings.scoring_json if settings else None) or {}
        beta_values = {key: float(value) for key, value in LEGACY_BETA_KICKER_RULES.items()}
        snapshot_kicker = snapshot.get("kicker") if isinstance(snapshot.get("kicker"), dict) else snapshot
        raw_kicker = raw.get("kicker") if isinstance(raw.get("kicker"), dict) else raw
        snapshot_values = {
            key: snapshot_kicker.get(key)
            for key in beta_values
        }
        raw_values = {key: raw_kicker.get(key) for key in beta_values}
        if (
            settings is not None
            and settings.scoring_locked_at is not None
            and snapshot_values == beta_values
            and raw_values == beta_values
        ):
            return "LEGACY_BETA_DEFAULT", "immutable beta scoring snapshot matches the former flat-three kicker default"
        if settings is not None and settings.scoring_locked_at is None and all(key in raw_kicker for key in beta_values):
            return "EXPLICIT_OR_LEGACY_UNPROVEN", "flat rules are stored but no immutable creation snapshot proves commissioner intent"
        return "UNKNOWN", "no immutable creation snapshot proves whether flat field goals were selected or inherited"

    leagues = db.query(League).filter(League.season_year == season, League.status.notin_(("cancelled", "archived"))).all()
    flat: list[dict[str, Any]] = []
    for league in leagues:
        settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).one_or_none()
        try:
            rules = validate_scoring_rules((settings.scoring_json if settings else {}) or {}).kicker
        except ScoringRulesValidationError:
            continue
        field_goal_values = [rules[key] for key in ("fg_made_0_30", "fg_made_31_40", "fg_made_41_50", "fg_made_51_60", "fg_made_61_plus")]
        if field_goal_values != [3, 3, 3, 3, 3]:
            continue
        scored = db.query(PlayerWeekScore.id).filter(PlayerWeekScore.league_id == league.id).first() is not None
        status = (league.status or "").lower()
        phase = "already_scored" if scored else "pre_draft" if status in {"pre_draft", "draft_pending", "setup"} else "post_draft_pre_season"
        source, evidence = provenance(settings)
        flat.append({
            "league_id": league.id,
            "league_name": league.name,
            "phase": phase,
            "provenance": source,
            "provenance_evidence": evidence,
        })
    return {
        "total_official_leagues": len(leagues),
        "flat_fg_leagues": len(flat),
        "tiered_fg_leagues": len(leagues) - len(flat),
        "flat_fg": flat,
        "counts": {phase: sum(item["phase"] == phase for item in flat) for phase in ("pre_draft", "post_draft_pre_season", "already_scored")},
        "provenance_counts": {
            category: sum(item["provenance"] == category for item in flat)
            for category in ("LEGACY_BETA_DEFAULT", "EXPLICIT_OR_LEGACY_UNPROVEN", "UNKNOWN")
        },
    }
