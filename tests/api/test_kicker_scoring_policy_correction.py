from copy import deepcopy
from datetime import datetime, timezone

from collegefootballfantasy_api.app.domain.scoring_rules import KICKER_RULES, PREVIOUS_KICKER_RULES, validate_scoring_rules
from collegefootballfantasy_api.app.models.chat import ChatMessage
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_scoring_migration import LeagueScoringMigration
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.kicker_scoring_policy_correction import (
    MIGRATION_KEY,
    MIGRATION_REASON,
    apply_kicker_scoring_policy_correction,
    plan_kicker_scoring_policy_correction,
)


def _old_policy_settings(league_id: int, *, receptions: float = 1) -> LeagueSettings:
    raw = {"receptions": receptions, **PREVIOUS_KICKER_RULES}
    return LeagueSettings(
        league_id=league_id,
        scoring_json=deepcopy(raw),
        scoring_snapshot_json=deepcopy(raw),
        scoring_locked_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def _league_with_old_policy(db_session, *, name: str) -> tuple[League, LeagueSettings]:
    league = League(name=name, season_year=2026, status="pre_draft")
    db_session.add(league)
    db_session.flush()
    settings = _old_policy_settings(league.id)
    db_session.add(settings)
    db_session.flush()
    return league, settings


def test_plan_targets_only_the_former_policy_and_excludes_any_scored_league(db_session):
    eligible, _ = _league_with_old_policy(db_session, name="Eligible policy correction")
    scored, _ = _league_with_old_policy(db_session, name="Already scored policy correction")
    team = Team(league_id=scored.id, name="Scored Team")
    db_session.add(team)
    db_session.flush()
    db_session.add(TeamWeekScore(league_id=scored.id, team_id=team.id, season=2026, week=1, points_total=0))
    db_session.commit()

    plans = {plan.league_id: plan for plan in plan_kicker_scoring_policy_correction(db_session, season=2026)}

    assert plans[eligible.id].eligible is True
    assert plans[eligible.id].non_kicker_changed is False
    assert validate_scoring_rules(plans[eligible.id].after_scoring_json).kicker == KICKER_RULES
    assert plans[scored.id].eligible is False
    assert plans[scored.id].exclusion_reason == "league has official team-week scores"


def test_apply_preserves_snapshot_audits_every_write_and_is_idempotent(db_session):
    league, settings = _league_with_old_policy(db_session, name="Apply policy correction")
    original_snapshot = deepcopy(settings.scoring_snapshot_json)
    original_rules = deepcopy(settings.scoring_json)
    db_session.commit()

    first = apply_kicker_scoring_policy_correction(
        db_session, season=2026, now=datetime(2026, 8, 16, tzinfo=timezone.utc)
    )
    db_session.commit()
    db_session.refresh(settings)

    assert first["config_writes"] == first["audit_rows"] == first["system_notices"] == 1
    assert settings.scoring_snapshot_json == original_snapshot
    assert settings.scoring_json["receptions"] == original_rules["receptions"]
    assert validate_scoring_rules(settings.scoring_json).kicker == KICKER_RULES
    audit = db_session.query(LeagueScoringMigration).filter_by(league_id=league.id).one()
    assert audit.migration_key == MIGRATION_KEY
    assert audit.reason == MIGRATION_REASON
    assert audit.before_scoring_json == original_rules
    assert audit.before_scoring_snapshot_json == original_snapshot
    assert audit.after_scoring_json == settings.scoring_json
    assert db_session.query(ChatMessage).filter(ChatMessage.league_id == league.id).count() == 1

    second = apply_kicker_scoring_policy_correction(db_session, season=2026)
    db_session.commit()
    assert second["config_writes"] == second["audit_rows"] == second["system_notices"] == 0
    assert db_session.query(LeagueScoringMigration).filter_by(league_id=league.id).count() == 1
    assert db_session.query(ChatMessage).filter(ChatMessage.league_id == league.id).count() == 1


def test_new_field_goal_contract_is_three_three_four_five_five_with_no_miss_penalty():
    rules = validate_scoring_rules({"fg": 3, "xp": 1}).kicker

    assert rules == KICKER_RULES
    assert rules == {
        "fg_made_0_30": 3,
        "fg_made_31_40": 3,
        "fg_made_41_50": 4,
        "fg_made_51_60": 5,
        "fg_made_61_plus": 5,
        "xp_made": 1,
        "fg_missed": 0,
    }
