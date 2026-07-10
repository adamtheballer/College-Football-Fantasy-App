from pathlib import Path
from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.lineup_locking import player_is_locked_for_week
from collegefootballfantasy_api.app.services.team_provider_mapping import (
    upsert_team_provider_id,
    weekly_lock_readiness,
)


TEST_DIR = Path(__file__).resolve().parent


def test_lineup_locking_regressions_are_covered_by_route_and_scoring_tests():
    roster_tests = (TEST_DIR / "test_roster_workflows.py").read_text()
    scoring_tests = (TEST_DIR / "test_stat_finalization_corrections.py").read_text()

    assert "test_roster_mutations_block_locked_players_after_kickoff" in roster_tests
    assert "test_roster_mutations_allow_players_before_kickoff" in roster_tests
    assert "test_lineup_snapshot_updates_before_player_game_locks" in scoring_tests
    assert "test_lineup_snapshot_freezes_after_player_game_locks" in scoring_tests


def test_player_lock_uses_provider_team_id_when_display_names_differ(client, db_session):
    player = Player(name="Mapped Texas RB", position="RB", school="Texas")
    db_session.add(player)
    db_session.flush()
    upsert_team_provider_id(
        db_session,
        canonical_school="Texas",
        provider="sportsdata",
        provider_team_id="sd-texas",
        provider_team_name="Texas Longhorns",
    )
    db_session.add(
        Game(
            external_id="sd-game-1",
            provider="sportsdata",
            season=2026,
            week=1,
            start_date=datetime.now(timezone.utc) - timedelta(minutes=10),
            home_team="Longhorns",
            away_team="Sooners",
            home_provider_team_id="sd-texas",
            away_provider_team_id="sd-oklahoma",
        )
    )
    db_session.commit()

    assert player_is_locked_for_week(
        db_session,
        player=player,
        season=2026,
        week=1,
        now=datetime.now(timezone.utc),
    )


def test_power4_player_without_team_provider_mapping_is_not_name_locked(client, db_session):
    player = Player(name="Unmapped Texas RB", position="RB", school="Texas")
    db_session.add_all(
        [
            player,
            Game(
                external_id="legacy-name-game",
                season=2026,
                week=1,
                start_date=datetime.now(timezone.utc) - timedelta(minutes=10),
                home_team="Texas",
                away_team="Oklahoma",
            ),
        ]
    )
    db_session.commit()

    assert not player_is_locked_for_week(
        db_session,
        player=player,
        season=2026,
        week=1,
        now=datetime.now(timezone.utc),
    )


def test_weekly_lock_readiness_reports_mapping_game_and_start_date_gaps(client, db_session):
    db_session.add_all(
        [
            Player(name="Texas RB", position="RB", school="Texas"),
            Player(name="Oregon RB", position="RB", school="Oregon"),
            Player(name="Alabama WR", position="WR", school="Alabama"),
        ]
    )
    upsert_team_provider_id(db_session, canonical_school="Texas", provider="sportsdata", provider_team_id="sd-texas")
    upsert_team_provider_id(db_session, canonical_school="Oregon", provider="sportsdata", provider_team_id="sd-oregon")
    db_session.add(
        Game(
            external_id="missing-start",
            provider="sportsdata",
            season=2026,
            week=1,
            start_date=None,
            home_team="Texas",
            away_team="Oklahoma",
            home_provider_team_id="sd-texas",
            away_provider_team_id="sd-oklahoma",
        )
    )
    db_session.commit()

    report = weekly_lock_readiness(db_session, season=2026, week=1, provider="sportsdata")

    assert report.ready is False
    assert report.unmapped_schools == ["Alabama"]
    assert report.missing_game_or_bye == ["Oregon"]
    assert report.missing_start_dates[0]["school"] == "Texas"


def test_weekly_lock_readiness_accepts_inferred_bye_week(client, db_session):
    db_session.add(Player(name="Oregon RB", position="RB", school="Oregon"))
    upsert_team_provider_id(db_session, canonical_school="Oregon", provider="sportsdata", provider_team_id="sd-oregon")
    db_session.add_all(
        [
            Game(
                external_id="oregon-week-1",
                provider="sportsdata",
                season=2026,
                week=1,
                start_date=datetime.now(timezone.utc) + timedelta(days=1),
                home_team="Oregon",
                away_team="UCLA",
                home_provider_team_id="sd-oregon",
                away_provider_team_id="sd-ucla",
            ),
            Game(
                external_id="oregon-week-3",
                provider="sportsdata",
                season=2026,
                week=3,
                start_date=datetime.now(timezone.utc) + timedelta(days=15),
                home_team="Washington",
                away_team="Oregon",
                home_provider_team_id="sd-washington",
                away_provider_team_id="sd-oregon",
            ),
        ]
    )
    db_session.commit()

    report = weekly_lock_readiness(db_session, season=2026, week=2, provider="sportsdata")

    assert report.ready is True
    assert report.bye_schools == ["Oregon"]
