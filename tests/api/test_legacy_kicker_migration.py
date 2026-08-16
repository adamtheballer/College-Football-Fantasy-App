from copy import deepcopy
from datetime import datetime, timezone

from collegefootballfantasy_api.app.domain.scoring_rules import BETA_KICKER_RULES, KICKER_RULES, validate_scoring_rules
from collegefootballfantasy_api.app.models.chat import ChatMessage
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_scoring_migration import LeagueScoringMigration
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.services.legacy_kicker_migration import (
    MIGRATION_KEY,
    MIGRATION_REASON,
    apply_legacy_kicker_migration,
    plan_legacy_kicker_migration,
)


def _legacy_settings(league_id: int, *, receptions: float = 1) -> LeagueSettings:
    raw = {"receptions": receptions, **BETA_KICKER_RULES}
    return LeagueSettings(
        league_id=league_id,
        scoring_json=deepcopy(raw),
        scoring_snapshot_json=deepcopy(raw),
        scoring_locked_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def _league_with_legacy_scoring(db_session, *, name: str, status: str = "pre_draft") -> tuple[League, LeagueSettings]:
    league = League(name=name, season_year=2026, status=status)
    db_session.add(league)
    db_session.flush()
    settings = _legacy_settings(league.id)
    db_session.add(settings)
    db_session.flush()
    return league, settings


def test_dry_run_only_targets_proven_unscored_inactive_legacy_leagues(db_session):
    eligible, _ = _league_with_legacy_scoring(db_session, name="Eligible")
    scored, _ = _league_with_legacy_scoring(db_session, name="Scored")
    drafting, _ = _league_with_legacy_scoring(db_session, name="Drafting")
    db_session.add(PlayerWeekScore(league_id=scored.id, player_id=1, season=2026, week=1, fantasy_points=0))
    db_session.add(Draft(league_id=drafting.id, status="on_clock", draft_datetime_utc=datetime(2026, 8, 20, tzinfo=timezone.utc)))
    db_session.commit()

    plans = {plan.league_id: plan for plan in plan_legacy_kicker_migration(db_session, season=2026)}

    assert plans[eligible.id].eligible is True
    assert plans[eligible.id].non_kicker_changed is False
    assert plans[scored.id].exclusion_reason == "league has official player-week scores"
    assert plans[drafting.id].exclusion_reason == "league has an active draft"
    assert plans[eligible.id].before_scoring_json["receptions"] == plans[eligible.id].after_scoring_json["receptions"]
    assert validate_scoring_rules(plans[eligible.id].after_scoring_json).kicker == KICKER_RULES


def test_apply_preserves_immutable_snapshot_and_is_idempotent(db_session):
    league, settings = _league_with_legacy_scoring(db_session, name="Approved", status="active")
    original_snapshot = deepcopy(settings.scoring_snapshot_json)
    original_rules = deepcopy(settings.scoring_json)
    db_session.commit()

    first = apply_legacy_kicker_migration(db_session, season=2026, now=datetime(2026, 8, 16, tzinfo=timezone.utc))
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

    second = apply_legacy_kicker_migration(db_session, season=2026)
    db_session.commit()
    assert second["config_writes"] == second["audit_rows"] == second["system_notices"] == 0
    assert db_session.query(LeagueScoringMigration).filter_by(league_id=league.id).count() == 1
    assert db_session.query(ChatMessage).filter(ChatMessage.league_id == league.id).count() == 1


def test_unproven_flat_scoring_is_never_selected(db_session):
    league = League(name="Unproven", season_year=2026, status="pre_draft")
    db_session.add(league)
    db_session.flush()
    db_session.add(LeagueSettings(league_id=league.id, scoring_json={"receptions": 1, **BETA_KICKER_RULES}))
    db_session.commit()

    plans = plan_legacy_kicker_migration(db_session, season=2026)
    assert len(plans) == 1
    assert plans[0].eligible is False
    assert plans[0].exclusion_reason == "legacy provenance is not proven"
