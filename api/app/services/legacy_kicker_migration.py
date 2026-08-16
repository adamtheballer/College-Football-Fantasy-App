"""Safe, idempotent correction for inherited flat beta kicker scoring.

This is intentionally separate from live scoring.  It touches only approved
league settings, keeps the original beta snapshot immutable, and records a
versioned before/after audit row for every applied correction.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.scoring_rules import KICKER_RULES
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.chat import ChatMessage
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_scoring_migration import LeagueScoringMigration
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.services.chat_service import create_system_chat_message
from collegefootballfantasy_api.app.services.draft_service import ACTIVE_DRAFT_STATUSES
from collegefootballfantasy_api.app.services.live_scoring_readiness import flat_field_goal_league_audit


MIGRATION_KEY = "legacy-beta-kicker-scoring-v1"
MIGRATION_REASON = "LEGACY_BETA_KICKER_SCORING_CORRECTION"
SYSTEM_NOTICE = (
    "Scoring update: Kicker field-goal scoring has been updated to the official "
    "College Fantasy Football scoring rules before Week 1. No completed matchup scores were affected."
)


@dataclass(frozen=True)
class LegacyKickerMigrationPlan:
    league_id: int
    league_name: str
    phase: str
    eligible: bool
    exclusion_reason: str | None
    before_scoring_json: dict
    after_scoring_json: dict
    non_kicker_changed: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _with_canonical_kicker_rules(scoring_json: dict) -> dict:
    """Preserve the caller's scoring representation and change only kicker keys."""

    after = deepcopy(scoring_json)
    if isinstance(after.get("kicker"), dict):
        after["kicker"] = {**after["kicker"], **KICKER_RULES}
    else:
        after.update(KICKER_RULES)
    return after


def _without_kicker_rules(scoring_json: dict) -> dict:
    value = deepcopy(scoring_json)
    if isinstance(value.get("kicker"), dict):
        value["kicker"] = {
            key: rule
            for key, rule in value["kicker"].items()
            if key not in KICKER_RULES
        }
    else:
        for key in KICKER_RULES:
            value.pop(key, None)
    return value


def plan_legacy_kicker_migration(db: Session, *, season: int) -> list[LegacyKickerMigrationPlan]:
    """Return all proven legacy-flat targets with per-league safety eligibility."""

    audit = flat_field_goal_league_audit(db, season=season)
    plans: list[LegacyKickerMigrationPlan] = []
    for item in audit["flat_fg"]:
        league = db.get(League, item["league_id"])
        settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == item["league_id"]).one_or_none()
        if league is None or settings is None:
            continue
        scored = db.query(PlayerWeekScore.id).filter(PlayerWeekScore.league_id == league.id).first() is not None
        active_draft = (
            db.query(Draft.id)
            .filter(Draft.league_id == league.id, Draft.status.in_(ACTIVE_DRAFT_STATUSES))
            .first()
            is not None
        )
        exclusion_reason = None
        if item["provenance"] != "LEGACY_BETA_DEFAULT":
            exclusion_reason = "legacy provenance is not proven"
        elif scored:
            exclusion_reason = "league has official player-week scores"
        elif active_draft:
            exclusion_reason = "league has an active draft"
        before = deepcopy(settings.scoring_json or {})
        after = _with_canonical_kicker_rules(before)
        plans.append(
            LegacyKickerMigrationPlan(
                league_id=league.id,
                league_name=league.name,
                phase=item["phase"],
                eligible=exclusion_reason is None,
                exclusion_reason=exclusion_reason,
                before_scoring_json=before,
                after_scoring_json=after,
                non_kicker_changed=_without_kicker_rules(before) != _without_kicker_rules(after),
            )
        )
    return plans


def apply_legacy_kicker_migration(db: Session, *, season: int, now: datetime | None = None) -> dict:
    """Apply eligible plans in the caller's transaction and return exact write counts."""

    applied_at = now or _now()
    summary = {"config_writes": 0, "audit_rows": 0, "system_notices": 0, "excluded": [], "migrated": []}
    for plan in plan_legacy_kicker_migration(db, season=season):
        if not plan.eligible:
            summary["excluded"].append({"league_id": plan.league_id, "reason": plan.exclusion_reason})
            continue
        existing = (
            db.query(LeagueScoringMigration)
            .filter(LeagueScoringMigration.league_id == plan.league_id, LeagueScoringMigration.migration_key == MIGRATION_KEY)
            .one_or_none()
        )
        if existing is not None:
            continue
        settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == plan.league_id).with_for_update().one()
        before = deepcopy(settings.scoring_json or {})
        if before != plan.before_scoring_json:
            summary["excluded"].append({"league_id": plan.league_id, "reason": "settings changed after dry-run planning"})
            continue
        if db.query(PlayerWeekScore.id).filter(PlayerWeekScore.league_id == plan.league_id).first() is not None:
            summary["excluded"].append({"league_id": plan.league_id, "reason": "league gained official player-week scores"})
            continue
        if db.query(Draft.id).filter(Draft.league_id == plan.league_id, Draft.status.in_(ACTIVE_DRAFT_STATUSES)).first() is not None:
            summary["excluded"].append({"league_id": plan.league_id, "reason": "league draft became active"})
            continue
        settings.scoring_json = deepcopy(plan.after_scoring_json)
        db.add(
            LeagueScoringMigration(
                league_id=plan.league_id,
                league_settings_id=settings.id,
                migration_key=MIGRATION_KEY,
                reason=MIGRATION_REASON,
                before_scoring_json=before,
                before_scoring_snapshot_json=deepcopy(settings.scoring_snapshot_json),
                after_scoring_json=deepcopy(plan.after_scoring_json),
                applied_at=applied_at,
            )
        )
        event_key = f"league-scoring-migration:{MIGRATION_KEY}:{plan.league_id}"
        notice_exists = db.query(ChatMessage.id).filter(ChatMessage.event_key == event_key).first() is not None
        message = create_system_chat_message(
            db,
            league_id=plan.league_id,
            body=SYSTEM_NOTICE,
            metadata_json={"migration_key": MIGRATION_KEY, "reason": MIGRATION_REASON},
            event_key=event_key,
        )
        db.flush()
        summary["config_writes"] += 1
        summary["audit_rows"] += 1
        summary["system_notices"] += int(message is not None and not notice_exists)
        summary["migrated"].append(plan.league_id)
    return summary


def render_migration_plan(db: Session, *, season: int) -> dict:
    plans = plan_legacy_kicker_migration(db, season=season)
    return {
        "season": season,
        "migration_key": MIGRATION_KEY,
        "reason": MIGRATION_REASON,
        "plans": [asdict(plan) for plan in plans],
        "eligible": sum(plan.eligible for plan in plans),
        "excluded": sum(not plan.eligible for plan in plans),
    }
