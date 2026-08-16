"""Versioned, pre-Week-1 correction for the former tiered kicker policy.

The correction is deliberately separate from live scoring and from the legacy
flat-beta migration.  It can alter only leagues that still have the exact old
3/5/7/9/11 schedule and have no evidence of official scoring activity.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.scoring_rules import (
    KICKER_RULES,
    PREVIOUS_KICKER_RULES,
    ScoringRulesValidationError,
    validate_scoring_rules,
)
from collegefootballfantasy_api.app.models.chat import ChatMessage
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_scoring_migration import LeagueScoringMigration
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.chat_service import create_system_chat_message
from collegefootballfantasy_api.app.services.draft_service import ACTIVE_DRAFT_STATUSES


MIGRATION_KEY = "official-kicker-scoring-policy-v2"
MIGRATION_REASON = "OFFICIAL_KICKER_SCORING_POLICY_CORRECTION"
SYSTEM_NOTICE = (
    "Scoring update: Kicker field goals now score 3 points from 0–40 yards, 4 points from 41–50, "
    "and 5 points from 51+; extra points are 1 and missed field goals are 0. "
    "No completed matchup scores were affected."
)
_FIELD_GOAL_KEYS = (
    "fg_made_0_30",
    "fg_made_31_40",
    "fg_made_41_50",
    "fg_made_51_60",
    "fg_made_61_plus",
)


@dataclass(frozen=True)
class KickerScoringPolicyCorrectionPlan:
    league_id: int
    league_name: str
    eligible: bool
    exclusion_reason: str | None
    before_scoring_json: dict
    after_scoring_json: dict
    non_kicker_changed: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _raw_kicker_rules(scoring_json: dict) -> dict:
    nested = scoring_json.get("kicker")
    return nested if isinstance(nested, dict) else scoring_json


def _matches_previous_kicker_policy(scoring_json: dict) -> bool:
    """Match only the precise former 3/5/7/9/11 schedule.

    Some pre-correction settings did not explicitly persist ``fg_missed``.
    That omission was historically interpreted as -1, so it remains an
    approved target; any explicit non--1 value is excluded.
    """

    try:
        current = validate_scoring_rules(scoring_json).kicker
    except ScoringRulesValidationError:
        return False
    raw = _raw_kicker_rules(scoring_json)
    return (
        all(current[key] == PREVIOUS_KICKER_RULES[key] for key in (*_FIELD_GOAL_KEYS, "xp_made"))
        and raw.get("fg_missed") in (None, PREVIOUS_KICKER_RULES["fg_missed"])
    )


def _with_canonical_kicker_rules(scoring_json: dict) -> dict:
    after = deepcopy(scoring_json)
    if isinstance(after.get("kicker"), dict):
        after["kicker"] = {**after["kicker"], **KICKER_RULES}
    else:
        after.update(KICKER_RULES)
    return after


def _without_kicker_rules(scoring_json: dict) -> dict:
    value = deepcopy(scoring_json)
    if isinstance(value.get("kicker"), dict):
        value["kicker"] = {key: rule for key, rule in value["kicker"].items() if key not in KICKER_RULES}
    else:
        for key in KICKER_RULES:
            value.pop(key, None)
    return value


def _official_scoring_exclusion(db: Session, league_id: int) -> str | None:
    if db.query(PlayerWeekScore.id).filter(PlayerWeekScore.league_id == league_id).first() is not None:
        return "league has official player-week scores"
    if db.query(TeamWeekScore.id).filter(TeamWeekScore.league_id == league_id).first() is not None:
        return "league has official team-week scores"
    matchup_activity = (
        db.query(Matchup.id)
        .filter(
            Matchup.league_id == league_id,
            or_(
                Matchup.status.in_(("live", "final", "stat_corrected")),
                Matchup.home_score != 0,
                Matchup.away_score != 0,
            ),
        )
        .first()
    )
    if matchup_activity is not None:
        return "league has official matchup scoring activity"
    standing_activity = (
        db.query(Standing.id)
        .filter(
            Standing.league_id == league_id,
            or_(
                Standing.wins != 0,
                Standing.losses != 0,
                Standing.ties != 0,
                Standing.points_for != 0,
                Standing.points_against != 0,
            ),
        )
        .first()
    )
    if standing_activity is not None:
        return "league has official standings activity"
    return None


def _exclusion_reason(db: Session, league: League, settings: LeagueSettings) -> str | None:
    if not _matches_previous_kicker_policy(settings.scoring_json or {}):
        return "league does not have the precise former kicker policy"
    scoring_exclusion = _official_scoring_exclusion(db, league.id)
    if scoring_exclusion:
        return scoring_exclusion
    if (
        db.query(Draft.id)
        .filter(Draft.league_id == league.id, Draft.status.in_(ACTIVE_DRAFT_STATUSES))
        .first()
        is not None
    ):
        return "league has an active draft"
    return None


def plan_kicker_scoring_policy_correction(db: Session, *, season: int) -> list[KickerScoringPolicyCorrectionPlan]:
    """Produce a read-only plan for every exact pre-correction policy target."""

    plans: list[KickerScoringPolicyCorrectionPlan] = []
    leagues = (
        db.query(League)
        .filter(League.season_year == season, League.status.notin_(("cancelled", "archived")))
        .order_by(League.id.asc())
        .all()
    )
    for league in leagues:
        settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).one_or_none()
        if settings is None:
            continue
        before = deepcopy(settings.scoring_json or {})
        if not _matches_previous_kicker_policy(before):
            continue
        exclusion_reason = _exclusion_reason(db, league, settings)
        after = _with_canonical_kicker_rules(before)
        plans.append(
            KickerScoringPolicyCorrectionPlan(
                league_id=league.id,
                league_name=league.name,
                eligible=exclusion_reason is None,
                exclusion_reason=exclusion_reason,
                before_scoring_json=before,
                after_scoring_json=after,
                non_kicker_changed=_without_kicker_rules(before) != _without_kicker_rules(after),
            )
        )
    return plans


def apply_kicker_scoring_policy_correction(
    db: Session, *, season: int, now: datetime | None = None
) -> dict:
    """Apply eligible corrections atomically, with a unique audit row per league."""

    applied_at = now or _now()
    summary = {"config_writes": 0, "audit_rows": 0, "system_notices": 0, "excluded": [], "migrated": []}
    for plan in plan_kicker_scoring_policy_correction(db, season=season):
        if not plan.eligible:
            summary["excluded"].append({"league_id": plan.league_id, "reason": plan.exclusion_reason})
            continue
        existing = (
            db.query(LeagueScoringMigration)
            .filter(
                LeagueScoringMigration.league_id == plan.league_id,
                LeagueScoringMigration.migration_key == MIGRATION_KEY,
            )
            .one_or_none()
        )
        if existing is not None:
            continue
        settings = (
            db.query(LeagueSettings)
            .filter(LeagueSettings.league_id == plan.league_id)
            .with_for_update()
            .one()
        )
        before = deepcopy(settings.scoring_json or {})
        if before != plan.before_scoring_json:
            summary["excluded"].append({"league_id": plan.league_id, "reason": "settings changed after dry-run planning"})
            continue
        exclusion_reason = _exclusion_reason(db, db.get(League, plan.league_id), settings)
        if exclusion_reason is not None:
            summary["excluded"].append({"league_id": plan.league_id, "reason": exclusion_reason})
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


def render_kicker_scoring_policy_correction_plan(db: Session, *, season: int) -> dict:
    plans = plan_kicker_scoring_policy_correction(db, season=season)
    return {
        "season": season,
        "migration_key": MIGRATION_KEY,
        "reason": MIGRATION_REASON,
        "plans": [asdict(plan) for plan in plans],
        "eligible": sum(plan.eligible for plan in plans),
        "excluded": sum(not plan.eligible for plan in plans),
    }
