from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_waiver_availability import PlayerWaiverAvailability
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_period import WaiverPeriod
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.league_flow import LeagueSettingsInput, LeagueSettingsUpdate
from collegefootballfantasy_api.app.services.league_roster_matchup import build_waivers_view
from collegefootballfantasy_api.app.schemas.waiver import FreeAgentAdd
from collegefootballfantasy_api.app.services.waiver_service import (
    _next_waiver_process_time,
    add_free_agent,
    initialize_waiver_state_after_official_draft,
    process_waiver_claims_once,
    record_player_dropped_for_waivers,
)
import collegefootballfantasy_api.app.services.waiver_service as waiver_service


def canonical_player(name: str, position: str, school: str) -> Player:
    """Create a player that represents a reconciled snapshot import."""
    return Player(
        name=name,
        position=position,
        school=school,
        sheet_source_sheet_id="canonical-preseason:2026:test-fixture",
        sheet_projected_season_points=200.0,
    )


def _league_settings_payload() -> dict:
    return {
        "scoring_json": {},
        "roster_slots_json": {"QB": 1},
        "playoff_teams": 4,
        "waiver_type": "faab",
        "trade_review_type": "commissioner",
        "superflex_enabled": False,
        "kicker_enabled": False,
        "defense_enabled": False,
    }


def _freeze_free_agent_time(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Keep free-agent tests in the same CFB week as their completed window."""

    current = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(waiver_service, "_now", lambda: current)
    return current


def test_waiver_timezone_must_be_a_valid_iana_identifier():
    invalid = {**_league_settings_payload(), "waiver_timezone": "Eastern Time"}

    with pytest.raises(ValidationError, match="valid IANA timezone"):
        LeagueSettingsInput.model_validate(invalid)
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        LeagueSettingsUpdate.model_validate(invalid)


def test_waiver_schedule_is_isolated_per_league_and_preserves_dst_local_hour(db_session):
    """Two leagues may choose different local schedules without cross-talk."""
    east_owner = User(
        email="east-waiver-owner@example.com",
        first_name="East",
        password_hash="test",
        api_token="east-waiver-owner-token",
    )
    west_owner = User(
        email="west-waiver-owner@example.com",
        first_name="West",
        password_hash="test",
        api_token="west-waiver-owner-token",
    )
    db_session.add_all((east_owner, west_owner))
    db_session.flush()
    east_league = League(name="Eastern Waiver League", season_year=2026, commissioner_user_id=east_owner.id, max_teams=2)
    west_league = League(name="Pacific Waiver League", season_year=2026, commissioner_user_id=west_owner.id, max_teams=2)
    db_session.add_all((east_league, west_league))
    db_session.flush()
    east_settings = LeagueSettings(
        league_id=east_league.id,
        roster_slots_json={"QB": 1},
        waiver_processing_weekday=6,
        waiver_processing_hour=8,
        waiver_timezone="America/New_York",
    )
    west_settings = LeagueSettings(
        league_id=west_league.id,
        roster_slots_json={"QB": 1},
        waiver_processing_weekday=6,
        waiver_processing_hour=8,
        waiver_timezone="America/Los_Angeles",
    )
    db_session.add_all((east_settings, west_settings))
    db_session.flush()

    # The following Sunday crosses into U.S. daylight saving time.  Both
    # leagues must still process at 8:00 AM in their own local timezone.
    before_dst = datetime(2026, 3, 7, 18, 0, tzinfo=timezone.utc)
    east_due = _next_waiver_process_time(db_session, east_league, east_settings, now=before_dst)
    west_due = _next_waiver_process_time(db_session, west_league, west_settings, now=before_dst)

    assert east_due != west_due
    assert (east_due.astimezone(ZoneInfo("America/New_York")).weekday(), east_due.astimezone(ZoneInfo("America/New_York")).hour) == (6, 8)
    assert (west_due.astimezone(ZoneInfo("America/Los_Angeles")).weekday(), west_due.astimezone(ZoneInfo("America/Los_Angeles")).hour) == (6, 8)
    assert east_settings.next_waiver_run_at == east_due
    assert west_settings.next_waiver_run_at == west_due


def test_lifecycle_releases_each_leagues_custom_post_drop_hold_without_due_period(db_session):
    """A short hold must not wait for an unrelated weekly waiver run."""
    first_owner = User(
        email="short-hold-owner@example.com",
        first_name="Short",
        password_hash="test",
        api_token="short-hold-owner-token",
    )
    second_owner = User(
        email="long-hold-owner@example.com",
        first_name="Long",
        password_hash="test",
        api_token="long-hold-owner-token",
    )
    db_session.add_all((first_owner, second_owner))
    db_session.flush()
    first_league = League(name="Short Hold League", season_year=2026, commissioner_user_id=first_owner.id, max_teams=2)
    second_league = League(name="Long Hold League", season_year=2026, commissioner_user_id=second_owner.id, max_teams=2)
    db_session.add_all((first_league, second_league))
    db_session.flush()
    first_team = Team(league_id=first_league.id, name="Short Hold Team", owner_user_id=first_owner.id, owner_name="Short")
    second_team = Team(league_id=second_league.id, name="Long Hold Team", owner_user_id=second_owner.id, owner_name="Long")
    first_player = canonical_player("Short Hold Player", "QB", "Texas")
    second_player = canonical_player("Long Hold Player", "QB", "Oregon")
    first_settings = LeagueSettings(league_id=first_league.id, roster_slots_json={"QB": 1}, post_drop_waiver_hours=1)
    second_settings = LeagueSettings(league_id=second_league.id, roster_slots_json={"QB": 1}, post_drop_waiver_hours=48)
    db_session.add_all((first_team, second_team, first_player, second_player, first_settings, second_settings))
    db_session.flush()

    dropped_at = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
    record_player_dropped_for_waivers(
        db_session,
        league=first_league,
        player_id=first_player.id,
        team_id=first_team.id,
        transaction_id=None,
        now=dropped_at,
    )
    record_player_dropped_for_waivers(
        db_session,
        league=second_league,
        player_id=second_player.id,
        team_id=second_team.id,
        transaction_id=None,
        now=dropped_at,
    )
    db_session.commit()

    assert process_waiver_claims_once(db_session, now=dropped_at + timedelta(hours=2)) == {
        "processed": 0,
        "failed": 0,
        "pending": 0,
    }
    first_availability = db_session.query(PlayerWaiverAvailability).filter_by(
        league_id=first_league.id, player_id=first_player.id
    ).one()
    second_availability = db_session.query(PlayerWaiverAvailability).filter_by(
        league_id=second_league.id, player_id=second_player.id
    ).one()
    assert first_availability.state == "free_agent"
    assert second_availability.state == "waiver_locked"


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
    assert waiver_view.available_players[0].weekly_projected_fantasy_points is None
    assert waiver_view.available_players[0].projection_status == "BYE"


def test_waiver_pool_uses_verified_final_box_score_for_unrostered_player(db_session):
    user = User(email="final-waiver-owner@example.com", first_name="Final", password_hash="test", api_token="final-waiver-owner-token")
    db_session.add(user)
    db_session.flush()
    league = League(name="Final Waiver League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    team = Team(league_id=league.id, name="Final Waiver Team", owner_user_id=user.id, owner_name="Final")
    player = canonical_player("Final Score USC WR", "WR", "USC")
    scoreless_player = canonical_player("Scoreless USC WR", "WR", "USC")
    game = Game(
        season=2026,
        week=1,
        home_team="USC",
        away_team="Opponent",
        schedule_status="final",
        home_points=31,
        away_points=10,
    )
    db_session.add_all((team, LeagueSettings(league_id=league.id, roster_slots_json={"WR": 1}), player, scoreless_player, game))
    db_session.flush()
    db_session.add_all(
        (
            WeeklyProjection(player_id=player.id, season=2026, week=1, is_published=True, fantasy_points=11.5),
            WeeklyProjection(player_id=scoreless_player.id, season=2026, week=1, is_published=True, fantasy_points=4.5),
            PlayerGameStat(
                player_id=player.id,
                game_id=game.id,
                season=2026,
                week=1,
                source="espn_final_boxscore",
                stats={"receptions": 4, "rec_yards": 83, "rec_tds": 1},
            ),
        )
    )
    db_session.commit()

    waiver_view = build_waivers_view(db_session, league, user, selected_week=1)

    rows = {row.id: row for row in waiver_view.available_players}
    row = rows[player.id]
    assert row.weekly_projected_fantasy_points == 11.5
    assert row.final_fantasy_points == 18.3
    assert row.opponent == "Opponent"
    assert rows[scoreless_player.id].final_fantasy_points == 0.0


def test_waiver_pool_sorts_the_full_selected_week_projection_set_before_pagination(db_session):
    user = User(email="waiver-sort-owner@example.com", first_name="Sort", password_hash="test", api_token="waiver-sort-owner-token")
    league = League(name="Waiver Sort League", season_year=2026, commissioner_user_id=1, max_teams=1)
    db_session.add(user)
    db_session.flush()
    league.commissioner_user_id = user.id
    db_session.add(league)
    db_session.flush()
    db_session.add(Team(league_id=league.id, name="Waiver Sort Team", owner_user_id=user.id, owner_name="Sort"))
    high = canonical_player("High Week One", "QB", "Texas")
    low = canonical_player("Low Week One", "QB", "Texas")
    zero = canonical_player("Verified Zero", "QB", "Texas")
    bye = canonical_player("Bye Week One", "QB", "Texas")
    missing = canonical_player("Missing Week One", "QB", "Texas")
    db_session.add_all((high, low, zero, bye, missing))
    db_session.flush()
    db_session.add_all(
        (
            WeeklyProjection(player_id=high.id, season=2026, week=1, is_published=True, fantasy_points=24.0),
            WeeklyProjection(player_id=low.id, season=2026, week=1, is_published=True, fantasy_points=11.0),
            WeeklyProjection(player_id=zero.id, season=2026, week=1, is_published=True, fantasy_points=0.0),
            WeeklyProjection(player_id=bye.id, season=2026, week=1, is_published=True, projection_status="BYE", fantasy_points=0.0),
            WeeklyProjection(player_id=high.id, season=2026, week=2, is_published=True, fantasy_points=7.0),
            WeeklyProjection(player_id=low.id, season=2026, week=2, is_published=True, fantasy_points=30.0),
        )
    )
    db_session.commit()

    first_page = build_waivers_view(db_session, league, user, selected_week=1, limit=2, offset=0)
    second_page = build_waivers_view(db_session, league, user, selected_week=1, limit=2, offset=2)
    third_page = build_waivers_view(db_session, league, user, selected_week=1, limit=2, offset=4)
    week_two = build_waivers_view(db_session, league, user, selected_week=2, limit=2, offset=0)

    assert [row.id for row in first_page.available_players] == [high.id, low.id]
    assert [row.id for row in second_page.available_players] == [zero.id, bye.id]
    assert [row.id for row in third_page.available_players] == [missing.id]
    assert third_page.available_players[0].weekly_projected_fantasy_points is None
    assert [row.id for row in week_two.available_players] == [low.id, high.id]


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


def test_free_agent_add_fills_an_open_slot_without_charging_faab(client, db_session, monkeypatch):
    current = _freeze_free_agent_time(monkeypatch)
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
            opens_at=current - timedelta(days=2),
            closes_at=current - timedelta(days=1),
            processes_at=current - timedelta(days=1),
            status="completed",
            processed_at=current - timedelta(days=1),
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


def test_free_agent_add_accepts_untracked_player_after_waivers_clear(client, db_session, monkeypatch):
    current = _freeze_free_agent_time(monkeypatch)
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
                opens_at=current - timedelta(days=2),
                closes_at=current - timedelta(days=1),
                processes_at=current - timedelta(days=1),
                status="completed",
                processed_at=current - timedelta(days=1),
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
