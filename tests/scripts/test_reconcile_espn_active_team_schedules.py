from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import ProviderIdentityAudit
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from scripts.reconcile_espn_active_team_schedules import CanonicalEvent, apply_repairs, as_utc, plan_repairs


def _active_schedule(db_session) -> TeamSchedule:
    league = League(name="Schedule authority", season_year=2026, status="active")
    player = Player(name="Texas starter", school="Texas", position="QB")
    db_session.add_all([league, player])
    db_session.flush()
    team = Team(league_id=league.id, name="Team")
    db_session.add(team)
    db_session.flush()
    db_session.add(RosterEntry(league_id=league.id, team_id=team.id, player_id=player.id, slot="QB", slot_index=1, status="active"))
    legacy = Game(external_id="sheet-2026-w1-texas-vs-ohio-state", season=2026, week=1, home_team="Texas", away_team="Ohio State")
    db_session.add(legacy)
    db_session.flush()
    schedule = TeamSchedule(team_name="Texas", season=2026, week=1, game_id=legacy.id, opponent_name="Ohio State", location="home", is_bye=False)
    db_session.add(schedule)
    db_session.commit()
    return schedule


def _event() -> CanonicalEvent:
    return CanonicalEvent(
        event_id="401999001",
        season=2026,
        week=1,
        home_team="Texas",
        away_team="Ohio State",
        kickoff="2026-09-05T16:00:00+00:00",
        status="pre",
    )


def test_active_schedule_reconciliation_requires_existing_verified_event_and_is_idempotent(db_session):
    schedule = _active_schedule(db_session)
    canonical = Game(external_id="401999001", season=2026, week=1, home_team="Texas", away_team="Ohio State", start_date=datetime(2026, 9, 5, 16, tzinfo=timezone.utc), schedule_status="pre")
    db_session.add(canonical)
    db_session.commit()

    plans = plan_repairs(db_session, season=2026, week=1, events=[_event()])

    assert [plan.category for plan in plans] == ["SAFE_ID_AND_KICKOFF_REPAIR"]
    assert apply_repairs(db_session, plans) == 1
    db_session.commit()
    db_session.refresh(schedule)
    assert schedule.game_id == canonical.id
    assert as_utc(schedule.kickoff_at) == datetime(2026, 9, 5, 16, tzinfo=timezone.utc)
    assert db_session.query(ProviderIdentityAudit).filter_by(entity_id=schedule.id, action="attach_verified_espn_event").count() == 1

    assert [plan.category for plan in plan_repairs(db_session, season=2026, week=1, events=[_event()])] == ["HARMLESS_ALIAS_NORMALIZATION"]


def test_active_schedule_reconciliation_refuses_any_row_without_verified_evidence(db_session):
    _active_schedule(db_session)

    plans = plan_repairs(db_session, season=2026, week=1, events=[])

    assert [plan.category for plan in plans] == ["NO_VERIFIED_EVENT"]
    with pytest.raises(RuntimeError, match="non-safe schedule rows"):
        apply_repairs(db_session, plans)
