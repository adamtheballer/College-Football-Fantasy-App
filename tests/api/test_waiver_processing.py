from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_waiver_availability import PlayerWaiverAvailability
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_period import WaiverPeriod
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.services.league_roster_matchup import build_waivers_view
from collegefootballfantasy_api.app.schemas.waiver import FreeAgentAdd
from collegefootballfantasy_api.app.services.waiver_service import add_free_agent, process_waiver_claims_once


def test_due_waiver_processing_is_idempotent_with_league_serialization(client, db_session):
    user = User(
        email="waiver-owner@example.com",
        first_name="Waiver",
        password_hash="test",
        api_token="waiver-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Waiver Lifecycle League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    db_session.add(
        LeagueSettings(
            league_id=league.id,
            roster_slots_json={"QB": 1},
            waiver_type="faab",
            waiver_period_hours=24,
        )
    )
    team = Team(league_id=league.id, name="Waiver Team", owner_user_id=user.id, owner_name="Waiver")
    player = Player(name="Waiver Available QB", position="QB", school="Texas")
    drafted_player = Player(name="Drafted QB", position="QB", school="Oregon")
    db_session.add_all([team, player, drafted_player])
    db_session.flush()
    draft = Draft(league_id=league.id, draft_datetime_utc=datetime.now(timezone.utc), status="completed")
    db_session.add(draft)
    db_session.flush()
    db_session.add(
        DraftPick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=drafted_player.id,
            made_by_user_id=user.id,
            round_number=1,
            round_pick=1,
            overall_pick=1,
        )
    )
    due_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    period = WaiverPeriod(
        league_id=league.id,
        season=league.season_year,
        week=1,
        window_key="2026-week-1-test",
        opens_at=due_at - timedelta(days=1),
        closes_at=due_at,
        processes_at=due_at,
        status="open",
    )
    db_session.add(period)
    db_session.flush()
    claim = WaiverClaim(
        league_id=league.id,
        team_id=team.id,
        add_player_id=player.id,
        created_by_user_id=user.id,
        status="pending",
        season=league.season_year,
        processing_week=1,
        processing_window_id=period.window_key,
        waiver_period_id=period.id,
        preference_order=1,
        priority_snapshot=1,
        faab_bid=7,
        process_after=due_at,
    )
    db_session.add(claim)
    db_session.commit()

    assert process_waiver_claims_once(db_session) == {"processed": 1, "failed": 0, "pending": 0}
    assert process_waiver_claims_once(db_session) == {"processed": 0, "failed": 0, "pending": 0}
    awarded_entry = db_session.query(RosterEntry).filter_by(league_id=league.id, player_id=player.id).one()
    assert awarded_entry.slot == "QB"
    assert awarded_entry.slot_index == 1
    assert db_session.query(WaiverPriority).filter_by(league_id=league.id, team_id=team.id).one().faab_spent == 7

    waiver_view = build_waivers_view(db_session, league, user)
    assert waiver_view.waiver_priority == 1
    assert waiver_view.faab_remaining == 93
    assert waiver_view.waiver_rules["faab_budget"] == 100


def test_waiver_pool_includes_a_dropped_drafted_player(client, db_session):
    user = User(
        email="waiver-pool-owner@example.com",
        first_name="Pool",
        password_hash="test",
        api_token="waiver-pool-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Dropped Player Waiver League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    team = Team(league_id=league.id, name="Waiver Team", owner_user_id=user.id, owner_name="Pool")
    player = Player(name="Previously Drafted QB", position="QB", school="Ohio State")
    db_session.add_all((team, player))
    db_session.flush()
    db_session.add(
        LeagueSettings(
            league_id=league.id,
            roster_slots_json={"QB": 1},
            waiver_type="faab",
            waiver_period_hours=24,
        )
    )
    draft = Draft(
        league_id=league.id,
        draft_datetime_utc=datetime.now(timezone.utc),
        status="completed",
    )
    db_session.add(draft)
    db_session.flush()
    db_session.add(
        DraftPick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=player.id,
            made_by_user_id=user.id,
            round_number=1,
            round_pick=1,
            overall_pick=1,
        )
    )
    db_session.commit()

    waiver_view = build_waivers_view(db_session, league, user)

    assert [candidate.id for candidate in waiver_view.available_players] == [player.id]


def test_waiver_results_are_scoped_to_the_latest_completed_period(client, db_session):
    user = User(
        email="waiver-results-owner@example.com",
        first_name="Results",
        password_hash="test",
        api_token="waiver-results-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Waiver Results League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    db_session.add(LeagueSettings(league_id=league.id, roster_slots_json={"QB": 1}, waiver_type="faab"))
    team = Team(league_id=league.id, name="Results Team", owner_user_id=user.id, owner_name="Results")
    old_player = Player(name="Old Waiver Winner", position="QB", school="Texas")
    recent_player = Player(name="Recent Waiver Winner", position="QB", school="Oregon")
    db_session.add_all((team, old_player, recent_player))
    db_session.flush()
    now = datetime.now(timezone.utc)
    old_period = WaiverPeriod(
        league_id=league.id,
        season=2026,
        week=1,
        window_key="2026-week-1-completed",
        opens_at=now - timedelta(days=8),
        closes_at=now - timedelta(days=7),
        processes_at=now - timedelta(days=7),
        status="completed",
        processed_at=now - timedelta(days=7),
    )
    recent_period = WaiverPeriod(
        league_id=league.id,
        season=2026,
        week=2,
        window_key="2026-week-2-completed",
        opens_at=now - timedelta(days=2),
        closes_at=now - timedelta(days=1),
        processes_at=now - timedelta(days=1),
        status="completed",
        processed_at=now - timedelta(days=1),
    )
    next_period = WaiverPeriod(
        league_id=league.id,
        season=2026,
        week=3,
        window_key="2026-week-3-open",
        opens_at=now,
        closes_at=now + timedelta(days=1),
        processes_at=now + timedelta(days=1),
        status="open",
    )
    db_session.add_all((old_period, recent_period, next_period))
    db_session.flush()
    db_session.add_all(
        (
            WaiverClaim(
                league_id=league.id,
                team_id=team.id,
                add_player_id=old_player.id,
                created_by_user_id=user.id,
                status="won",
                season=2026,
                processing_week=1,
                processing_window_id=old_period.window_key,
                waiver_period_id=old_period.id,
                preference_order=1,
                faab_bid=4,
                winning_bid=4,
                processed_at=old_period.processed_at,
            ),
            WaiverClaim(
                league_id=league.id,
                team_id=team.id,
                add_player_id=recent_player.id,
                created_by_user_id=user.id,
                status="won",
                season=2026,
                processing_week=2,
                processing_window_id=recent_period.window_key,
                waiver_period_id=recent_period.id,
                preference_order=1,
                faab_bid=9,
                winning_bid=9,
                processed_at=recent_period.processed_at,
            ),
        )
    )
    db_session.commit()

    waiver_view = build_waivers_view(db_session, league, user)

    assert waiver_view.current_period is not None
    assert waiver_view.current_period.id == next_period.id
    assert waiver_view.results_period is not None
    assert waiver_view.results_period.id == recent_period.id
    assert [claim.add_player_id for claim in waiver_view.results] == [recent_player.id]


def test_free_agent_add_fills_an_open_slot_without_charging_faab(client, db_session):
    user = User(
        email="free-agent-owner@example.com",
        first_name="Free",
        password_hash="test",
        api_token="free-agent-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Free Agent League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    settings = LeagueSettings(league_id=league.id, roster_slots_json={"QB": 1}, waiver_type="faab")
    team = Team(league_id=league.id, name="Free Agent Team", owner_user_id=user.id, owner_name="Free")
    player = Player(name="Available Free Agent QB", position="QB", school="Texas")
    db_session.add_all((settings, team, player))
    db_session.flush()
    db_session.add(
        WaiverPeriod(
            league_id=league.id,
            season=2026,
            week=1,
            window_key="2026-week-1-completed-free-agent",
            opens_at=datetime.now(timezone.utc) - timedelta(days=2),
            closes_at=datetime.now(timezone.utc) - timedelta(days=1),
            processes_at=datetime.now(timezone.utc) - timedelta(days=1),
            status="completed",
            processed_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db_session.add(
        PlayerWaiverAvailability(
            league_id=league.id,
            player_id=player.id,
            state="free_agent",
        )
    )
    db_session.commit()

    result = add_free_agent(
        db_session,
        league=league,
        current_user=user,
        player_id=player.id,
        payload=FreeAgentAdd(team_id=team.id),
    )

    entry = db_session.get(RosterEntry, result.roster_entry_id)
    availability = (
        db_session.query(PlayerWaiverAvailability)
        .filter_by(league_id=league.id, player_id=player.id)
        .one()
    )
    assert entry is not None
    assert (entry.slot, entry.slot_index) == ("QB", 1)
    assert availability.state == "rostered"
    assert db_session.query(WaiverPriority).filter_by(league_id=league.id, team_id=team.id).count() == 0


def test_free_agent_add_accepts_untracked_player_after_waivers_clear(client, db_session):
    user = User(
        email="untracked-free-agent-owner@example.com",
        first_name="Untracked",
        password_hash="test",
        api_token="untracked-free-agent-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Untracked Free Agent League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    team = Team(league_id=league.id, name="Untracked Team", owner_user_id=user.id, owner_name="Untracked")
    player = Player(name="Untracked Free Agent QB", position="QB", school="Utah")
    db_session.add_all(
        (
            LeagueSettings(league_id=league.id, roster_slots_json={"QB": 1}, waiver_type="faab"),
            team,
            player,
            WaiverPeriod(
                league_id=league.id,
                season=2026,
                week=1,
                window_key="2026-week-1-cleared-untracked",
                opens_at=datetime.now(timezone.utc) - timedelta(days=2),
                closes_at=datetime.now(timezone.utc) - timedelta(days=1),
                processes_at=datetime.now(timezone.utc) - timedelta(days=1),
                status="completed",
                processed_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
        )
    )
    db_session.commit()

    result = add_free_agent(
        db_session,
        league=league,
        current_user=user,
        player_id=player.id,
        payload=FreeAgentAdd(team_id=team.id),
    )

    assert db_session.get(RosterEntry, result.roster_entry_id).player_id == player.id
    assert (
        db_session.query(PlayerWaiverAvailability)
        .filter_by(league_id=league.id, player_id=player.id)
        .one()
        .state
        == "rostered"
    )


def test_untracked_player_cannot_be_added_until_waivers_have_cleared(client, db_session):
    user = User(
        email="pre-clear-free-agent-owner@example.com",
        first_name="PreClear",
        password_hash="test",
        api_token="pre-clear-free-agent-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Pre-Clear Free Agent League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    team = Team(league_id=league.id, name="Pre-Clear Team", owner_user_id=user.id, owner_name="PreClear")
    player = Player(name="Pre-Clear QB", position="QB", school="Arizona")
    db_session.add_all(
        (
            LeagueSettings(league_id=league.id, roster_slots_json={"QB": 1}, waiver_type="faab"),
            team,
            player,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException, match="currently available on waivers"):
        add_free_agent(
            db_session,
            league=league,
            current_user=user,
            player_id=player.id,
            payload=FreeAgentAdd(team_id=team.id),
        )
