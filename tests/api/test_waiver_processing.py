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
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.league_roster_matchup import build_waivers_view
from collegefootballfantasy_api.app.schemas.waiver import FreeAgentAdd
from collegefootballfantasy_api.app.services.waiver_service import (
    add_free_agent,
    initialize_waiver_state_after_official_draft,
    process_waiver_claims_once,
)


def canonical_player(name: str, position: str, school: str) -> Player:
    """Create a player that represents a reconciled snapshot import."""
    return Player(
        name=name,
        position=position,
        school=school,
        sheet_source_sheet_id="canonical-preseason:2026:test-fixture",
        sheet_projected_season_points=200.0,
    )


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
    player = canonical_player("Waiver Available QB", "QB", "Texas")
    drafted_player = canonical_player("Drafted QB", "QB", "Oregon")
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

    waiver_view = build_waivers_view(db_session, league, user, limit=1000)
    assert waiver_view.waiver_priority == 1
    assert waiver_view.faab_remaining == 93
    assert waiver_view.waiver_rules["faab_budget"] == 100


def test_completed_draft_adopts_valid_legacy_priorities_without_reordering(db_session):
    user = User(
        email="legacy-priority-owner@example.com",
        first_name="Legacy",
        password_hash="test",
        api_token="legacy-priority-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Legacy Priority League", season_year=2026, commissioner_user_id=user.id, max_teams=2)
    db_session.add(league)
    db_session.flush()
    settings = LeagueSettings(league_id=league.id, roster_slots_json={"QB": 1}, waiver_type="faab")
    first_team = Team(league_id=league.id, name="First Team", owner_user_id=user.id, owner_name="Legacy")
    second_team = Team(league_id=league.id, name="Second Team", owner_name="Second")
    first_player = canonical_player("First Drafted QB", "QB", "Texas")
    second_player = canonical_player("Second Drafted QB", "QB", "Oregon")
    db_session.add_all((settings, first_team, second_team, first_player, second_player))
    db_session.flush()
    draft = Draft(league_id=league.id, draft_datetime_utc=datetime.now(timezone.utc), status="completed")
    db_session.add(draft)
    db_session.flush()
    db_session.add_all(
        (
            DraftPick(
                draft_id=draft.id,
                team_id=first_team.id,
                player_id=first_player.id,
                made_by_user_id=user.id,
                round_number=1,
                round_pick=1,
                overall_pick=1,
            ),
            DraftPick(
                draft_id=draft.id,
                team_id=second_team.id,
                player_id=second_player.id,
                made_by_user_id=user.id,
                round_number=1,
                round_pick=2,
                overall_pick=2,
            ),
        )
    )
    # These rows represent a pre-marker migration backfill. Their order and
    # FAAB balances must be preserved when the marker is reconciled.
    db_session.add_all(
        (
            WaiverPriority(
                league_id=league.id,
                team_id=second_team.id,
                priority=1,
                faab_budget=100,
                faab_spent=0,
            ),
            WaiverPriority(
                league_id=league.id,
                team_id=first_team.id,
                priority=2,
                faab_budget=100,
                faab_spent=17,
            ),
        )
    )
    db_session.commit()

    priorities = initialize_waiver_state_after_official_draft(db_session, league)
    db_session.commit()
    db_session.refresh(settings)

    assert settings.waiver_initialized_at is not None
    assert priorities[second_team.id].priority == 1
    assert priorities[first_team.id].priority == 2
    assert priorities[first_team.id].faab_spent == 17


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
    player = canonical_player("Previously Drafted QB", "QB", "Ohio State")
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


def test_waiver_pool_remains_available_when_a_legacy_claim_has_no_period(db_session):
    """A pre-ledger claim cannot be allowed to hide every available player."""
    user = User(
        email="legacy-claim-owner@example.com",
        first_name="Legacy",
        password_hash="test",
        api_token="legacy-claim-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Legacy Claim Waiver League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    team = Team(league=league, name="Legacy Team", owner_user_id=user.id, owner_name="Legacy")
    available_player = canonical_player("Still Available QB", "QB", "Texas")
    legacy_claim_player = canonical_player("Legacy Claim QB", "QB", "Oregon")
    db_session.add_all((league, team, available_player, legacy_claim_player))
    db_session.flush()
    db_session.add(LeagueSettings(league_id=league.id, roster_slots_json={"QB": 1}, waiver_type="faab"))
    db_session.add(
        WaiverClaim(
            league_id=league.id,
            team_id=team.id,
            add_player_id=legacy_claim_player.id,
            created_by_user_id=user.id,
            status="cancelled",
            season=2026,
            processing_week=1,
            processing_window_id="legacy",
            # Intentionally omitted: historical claims predate WaiverPeriod.
            preference_order=1,
            faab_bid=0,
        )
    )
    db_session.commit()

    waiver_view = build_waivers_view(db_session, league, user)

    assert {player.id for player in waiver_view.available_players} == {available_player.id, legacy_claim_player.id}
    assert len(waiver_view.claims) == 1
    assert waiver_view.claims[0].waiver_period_id is None


def test_waiver_pool_surfaces_bye_status_instead_of_an_ambiguous_zero(db_session):
    user = User(
        email="bye-projection-owner@example.com",
        first_name="Bye",
        password_hash="test",
        api_token="bye-projection-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Bye Projection League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    team = Team(league=league, name="Bye Projection Team", owner_user_id=user.id, owner_name="Bye")
    player = canonical_player("Week One Bye RB", "RB", "North Carolina")
    db_session.add_all((league, team, player))
    db_session.flush()
    db_session.add(
        WeeklyProjection(
            player_id=player.id,
            season=2026,
            week=1,
            projection_version="FINAL",
            is_published=True,
            projection_status="BYE",
            fantasy_points=0.0,
        )
    )
    db_session.commit()

    waiver_view = build_waivers_view(db_session, league, user, selected_week=1)

    assert len(waiver_view.available_players) == 1
    assert waiver_view.available_players[0].weekly_projected_fantasy_points == 0.0
    assert waiver_view.available_players[0].projection_status == "BYE"


def test_waiver_pool_returns_the_complete_beta_player_universe(db_session):
    user = User(
        email="full-waiver-pool-owner@example.com",
        first_name="Full Pool",
        password_hash="test",
        api_token="full-waiver-pool-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Full Waiver Pool League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    db_session.add(Team(league_id=league.id, name="Full Pool Team", owner_user_id=user.id, owner_name="Full Pool"))
    players = [
        canonical_player(f"Complete Pool Player {index}", "QB", "Texas")
        for index in range(101)
    ]
    db_session.add_all(players)
    db_session.commit()

    waiver_view = build_waivers_view(db_session, league, user, limit=1000)

    assert waiver_view.total_available == 101
    assert len(waiver_view.available_players) == 101


def test_waiver_pool_and_claims_reject_legacy_provider_players(db_session):
    """A Power 4 provider row is not eligible unless snapshot-reconciled."""
    user = User(
        email="canonical-waiver-owner@example.com",
        first_name="Canonical",
        password_hash="test",
        api_token="canonical-waiver-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Canonical Waiver League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    team = Team(league_id=league.id, name="Canonical Team", owner_user_id=user.id, owner_name="Canonical")
    canonical = canonical_player("Reviewed Waiver QB", "QB", "Texas")
    legacy = Player(
        name="Legacy Provider QB",
        position="QB",
        school="Texas",
        sheet_source_sheet_id="sportsdata:2026:legacy",
        sheet_projected_season_points=999.0,
    )
    db_session.add_all((LeagueSettings(league_id=league.id, roster_slots_json={"QB": 1}), team, canonical, legacy))
    db_session.commit()

    waiver_view = build_waivers_view(db_session, league, user)
    assert [candidate.id for candidate in waiver_view.available_players] == [canonical.id]

    with pytest.raises(HTTPException, match="approved waiver pool"):
        add_free_agent(
            db_session,
            league=league,
            current_user=user,
            player_id=legacy.id,
            payload=FreeAgentAdd(team_id=team.id),
        )


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
    old_player = canonical_player("Old Waiver Winner", "QB", "Texas")
    recent_player = canonical_player("Recent Waiver Winner", "QB", "Oregon")
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
    player = canonical_player("Available Free Agent QB", "QB", "Texas")
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
    player = canonical_player("Untracked Free Agent QB", "QB", "Utah")
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
    player = canonical_player("Pre-Clear QB", "QB", "Arizona")
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
