from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.provider_identity import ProviderIdentityAudit
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.provider_identity import ProviderIdentityConflict
from scripts.reconcile_espn_schedule_conflicts import ScheduleDecision, reconcile_decisions


def _decision() -> ScheduleDecision:
    return ScheduleDecision(
        team_name="USC", season=2026, week=1, expected_game_external_id="sheet-2026-w1-usc-vs-fresno-state",
        replacement_event_id="401864494", home_team="USC", away_team="San José State",
        kickoff="2026-08-29T19:00:00+00:00", status="pre", evidence={"scoreboard_sha256": "scoreboard-hash"},
    )


def test_reconciliation_updates_the_existing_game_in_place_and_audits_it(db_session):
    game = Game(external_id="sheet-2026-w1-usc-vs-fresno-state", season=2026, week=1, home_team="USC", away_team="Fresno State")
    db_session.add(game)
    db_session.flush()
    schedule = TeamSchedule(team_name="USC", season=2026, week=1, game_id=game.id, opponent_name="Fresno State", location="home", is_bye=False)
    db_session.add(schedule)
    db_session.flush()

    assert reconcile_decisions(db_session, [_decision()]) == 1

    assert schedule.game_id == game.id
    assert game.external_id == "401864494"
    assert game.away_team == "San José State"
    assert game.start_date == datetime(2026, 8, 29, 19, tzinfo=timezone.utc)
    assert schedule.opponent_name == "San José State"
    audit = db_session.query(ProviderIdentityAudit).filter_by(entity_id=schedule.id, action="replace_verified_schedule").one()
    assert audit.before_state["game"]["away_team"] == "Fresno State"
    assert audit.after_state["evidence"]["scoreboard_sha256"] == "scoreboard-hash"


def test_reconciliation_refuses_an_unexpected_legacy_schedule(db_session):
    game = Game(external_id="different", season=2026, week=1, home_team="USC", away_team="Fresno State")
    db_session.add(game)
    db_session.flush()
    db_session.add(TeamSchedule(team_name="USC", season=2026, week=1, game_id=game.id, location="home", is_bye=False))
    db_session.flush()

    with pytest.raises(ProviderIdentityConflict, match="unexpected legacy game"):
        reconcile_decisions(db_session, [_decision()])
