from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.worker_heartbeat import WorkerHeartbeat
from collegefootballfantasy_api.app.services.live_scoring_readiness import (
    PublicScoringPreflightError,
    assert_public_scoring_ready,
    ensure_official_acquisition_identity,
    flat_field_goal_league_audit,
    public_scoring_preflight,
    scoring_operations_report,
)


NOW = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)


def _ready_baseline(db_session):
    league = League(name="Readiness League", season_year=2026, status="active")
    db_session.add(league)
    db_session.flush()
    db_session.add(LeagueSettings(league_id=league.id, scoring_json={}))
    db_session.add(Game(external_id="401", season=2026, week=1, home_team="Texas", away_team="Ohio State", start_date=NOW))
    db_session.add(WorkerHeartbeat(worker_name="espn_scoring_processor", status="healthy", heartbeat_at=NOW))
    db_session.commit()
    return league


def test_public_preflight_refuses_an_unresolved_active_starter(db_session):
    league = _ready_baseline(db_session)
    player = Player(name="Unresolved Starter", school="Texas", position="WR")
    db_session.add(player)
    db_session.flush()
    team = Team(league_id=league.id, name="Team")
    db_session.add(team)
    db_session.flush()
    db_session.add(LineupWeekSnapshot(league_id=league.id, team_id=team.id, player_id=player.id, season=2026, week=1, slot="WR", is_starter=True))
    db_session.commit()

    report = public_scoring_preflight(db_session, season=2026, week=1, now=NOW + timedelta(seconds=10))

    assert report["ready"] is False
    assert report["reason_codes"] == ["UNRESOLVED_STARTER_ESPN_ID"]
    assert report["unresolved_starters"] == [{
        "player_id": player.id, "name": "Unresolved Starter", "school": "Texas", "position": "WR",
        "league_id": league.id, "week": 1, "slot": "WR", "reason": "UNRESOLVED_STARTER_ESPN_ID",
    }]
    with pytest.raises(PublicScoringPreflightError, match="UNRESOLVED_STARTER_ESPN_ID"):
        assert_public_scoring_ready(db_session, season=2026, week=1, now=NOW + timedelta(seconds=10))


def test_public_preflight_accepts_verified_starter_and_healthy_dependencies(db_session):
    league = _ready_baseline(db_session)
    player = Player(name="Verified Starter", school="Texas", position="QB")
    db_session.add(player)
    db_session.flush()
    team = Team(league_id=league.id, name="Team")
    db_session.add(team)
    db_session.flush()
    db_session.add_all([
        PlayerProviderId(player_id=player.id, provider="espn", provider_player_id="123", verification_status="verified"),
        LineupWeekSnapshot(league_id=league.id, team_id=team.id, player_id=player.id, season=2026, week=1, slot="QB", is_starter=True),
    ])
    db_session.commit()

    report = public_scoring_preflight(db_session, season=2026, week=1, now=NOW + timedelta(seconds=10))

    assert report["ready"] is True
    assert report["reason_codes"] == []


def test_public_preflight_uses_completed_opening_game_before_later_week_one_placeholder(db_session):
    """A Week 1 placeholder cannot block the rest of the live scoring slate.

    USC's late Week 1 game is a real player-card/game-log event, but its final
    Week 0 opener is the only game eligible for fantasy Week 1 scoring.
    """
    league = _ready_baseline(db_session)
    player = Player(name="USC Starter", school="USC", position="RB")
    db_session.add(player)
    db_session.flush()
    team = Team(league_id=league.id, name="USC Team")
    db_session.add(team)
    db_session.flush()
    db_session.add(RosterEntry(
        league_id=league.id,
        team_id=team.id,
        player_id=player.id,
        slot="RB",
        status="active",
    ))
    opening_game = Game(
        external_id="401864494",
        season=2026,
        week=0,
        season_type="regular",
        schedule_status="final",
        home_team="USC",
        away_team="San Jose State",
        start_date=datetime(2026, 8, 29, 19, 0, tzinfo=timezone.utc),
    )
    later_week_one_game = Game(
        external_id="sealed-2026-w1-usc-fresno-state",
        season=2026,
        week=1,
        season_type="regular",
        schedule_status="pre",
        home_team="USC",
        away_team="Fresno State",
        start_date=datetime(2026, 9, 5, 1, 0, tzinfo=timezone.utc),
    )
    db_session.add_all([opening_game, later_week_one_game])
    db_session.flush()
    db_session.add_all([
        TeamSchedule(
            team_name="USC", season=2026, week=0, game_id=opening_game.id,
            opponent_name="San Jose State", location="home", kickoff_at=opening_game.start_date,
        ),
        TeamSchedule(
            team_name="USC", season=2026, week=1, game_id=later_week_one_game.id,
            opponent_name="Fresno State", location="home", kickoff_at=later_week_one_game.start_date,
        ),
    ])
    db_session.commit()

    report = public_scoring_preflight(db_session, season=2026, week=1, now=NOW + timedelta(seconds=10))

    assert report["ready"] is True
    assert report["reason_codes"] == []


def test_public_preflight_still_rejects_an_unverified_selected_scoring_game(db_session):
    league = _ready_baseline(db_session)
    player = Player(name="Unverified Game Starter", school="USC", position="RB")
    db_session.add(player)
    db_session.flush()
    team = Team(league_id=league.id, name="USC Team")
    db_session.add(team)
    db_session.flush()
    db_session.add(RosterEntry(
        league_id=league.id,
        team_id=team.id,
        player_id=player.id,
        slot="RB",
        status="active",
    ))
    unverified_game = Game(
        external_id="sealed-2026-w1-usc-fresno-state",
        season=2026,
        week=1,
        season_type="regular",
        schedule_status="pre",
        home_team="USC",
        away_team="Fresno State",
        start_date=datetime(2026, 9, 5, 1, 0, tzinfo=timezone.utc),
    )
    db_session.add(unverified_game)
    db_session.flush()
    db_session.add(TeamSchedule(
        team_name="USC", season=2026, week=1, game_id=unverified_game.id,
        opponent_name="Fresno State", location="home", kickoff_at=unverified_game.start_date,
    ))
    db_session.commit()

    report = public_scoring_preflight(db_session, season=2026, week=1, now=NOW + timedelta(seconds=10))

    assert report["ready"] is False
    assert report["reason_codes"] == ["UNVERIFIED_ESPN_GAME_ID"]


def test_official_acquisition_guard_blocks_only_unverified_players_when_enabled(db_session, monkeypatch):
    league = League(name="Official League", season_year=2026, status="active")
    unverified = Player(name="Identity Pending", school="Texas", position="WR")
    verified = Player(name="Identity Ready", school="Texas", position="QB")
    db_session.add_all([league, unverified, verified])
    db_session.flush()
    db_session.add(
        PlayerProviderId(
            player_id=verified.id,
            provider="espn",
            provider_player_id="456",
            verification_status="verified",
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "live_scoring_identity_guard_enabled", True)

    with pytest.raises(HTTPException) as error:
        ensure_official_acquisition_identity(db_session, league=league, player=unverified)

    assert error.value.status_code == 409
    assert error.value.detail.startswith("Live scoring identity pending")
    ensure_official_acquisition_identity(db_session, league=league, player=verified)


def test_operations_report_surfaces_provider_failures_without_idle_alert_spam(db_session):
    _ready_baseline(db_session)
    db_session.add(ProviderGamePoll(
        provider="espn", provider_game_id="401", season=2026, week=1, status="delayed", failure_count=3,
        error_message="HTTP 429 timeout", next_poll_at=NOW - timedelta(seconds=1),
    ))
    db_session.commit()

    report = scoring_operations_report(db_session, season=2026, week=1, now=NOW + timedelta(seconds=10))

    assert report["game_polling"]["http_429_count"] == 1
    assert report["game_polling"]["timeout_count"] == 1
    assert {alert["code"] for alert in report["alerts"]} == {
        "REPEATED_GAME_POLL_FAILURE", "ESPN_RATE_LIMIT_429", "ESPN_TIMEOUT", "PROVIDER_DATA_DELAYED",
    }


def test_flat_field_goal_audit_never_changes_league_rules(db_session):
    flat = League(name="Legacy Flat FG", season_year=2026, status="pre_draft")
    tiered = League(name="Tiered FG", season_year=2026, status="active")
    db_session.add_all([flat, tiered])
    db_session.flush()
    flat_settings = LeagueSettings(league_id=flat.id, scoring_json={"kicker": {"fg_made_0_30": 3, "fg_made_31_40": 3, "fg_made_41_50": 3, "fg_made_51_60": 3, "fg_made_61_plus": 3}})
    db_session.add_all([flat_settings, LeagueSettings(league_id=tiered.id, scoring_json={})])
    db_session.commit()

    report = flat_field_goal_league_audit(db_session, season=2026)

    assert report["total_official_leagues"] == 2
    assert report["flat_fg_leagues"] == 1
    assert report["counts"]["pre_draft"] == 1
    assert report["provenance_counts"] == {"LEGACY_BETA_DEFAULT": 0, "EXPLICIT_OR_LEGACY_UNPROVEN": 0, "UNKNOWN": 1}
    assert db_session.get(LeagueSettings, flat_settings.id).scoring_json["kicker"]["fg_made_31_40"] == 3


def test_flat_field_goal_audit_proves_legacy_beta_default_from_locked_snapshot(db_session):
    league = League(name="Locked beta league", season_year=2026, status="pre_draft")
    db_session.add(league)
    db_session.flush()
    flat_beta = {
        "fg_made_0_30": 3,
        "fg_made_31_40": 3,
        "fg_made_41_50": 3,
        "fg_made_51_60": 3,
        "fg_made_61_plus": 3,
        "xp_made": 1,
    }
    db_session.add(LeagueSettings(
        league_id=league.id,
        scoring_json=flat_beta,
        scoring_snapshot_json=flat_beta,
        scoring_locked_at=NOW,
    ))
    db_session.commit()

    report = flat_field_goal_league_audit(db_session, season=2026)

    assert report["provenance_counts"] == {"LEGACY_BETA_DEFAULT": 1, "EXPLICIT_OR_LEGACY_UNPROVEN": 0, "UNKNOWN": 0}
    assert report["flat_fg"][0]["provenance"] == "LEGACY_BETA_DEFAULT"
