from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll, ProviderGameSnapshot
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId, UnmatchedProviderRow
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.worker_heartbeat import WorkerHeartbeat
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.espn_stats_sync import UnresolvedKickerDistanceError, normalize_espn_summary_player_stats
from collegefootballfantasy_api.app.services.espn_live_scoring import (
    MAX_TRANSIENT_GAME_RETRY_SECONDS,
    MIN_GAME_POLL_INTERVAL_SECONDS,
    ProviderDataIncompleteError,
    SnapshotOrderMetadata,
    _failure_policy,
    _event_status,
    claim_due_espn_games,
    classify_snapshot_order,
    discover_relevant_espn_games,
    certify_espn_matchup_finality,
    espn_week_freshness,
    queue_accepted_espn_long_play_notifications,
    run_espn_scoring_cycle,
)
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.integrations.espn import ESPNProviderResponse
from collegefootballfantasy_api.app.services.live_scoring_readiness import PublicScoringPreflightError
import scripts.run_espn_scoring_worker as scoring_worker
from tests.api.scoring_helpers import create_scoring_fixture
from tests.api.test_espn_boxscores import espn_summary_payload


NOW = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class FakeLiveESPN:
    def __init__(self, summary=None, error=None, response_metadata=None):
        self.summary = summary or espn_summary_payload()
        self.error = error
        self.response_metadata = response_metadata or {}
        self.scoreboard_calls = 0
        self.summary_calls = 0

    def get_scoreboard_events(self, *, season, week):
        self.scoreboard_calls += 1
        return [
            {
                "id": "401",
                "status": {"type": {"state": "in", "completed": False}},
                "competitions": [{"competitors": [{"team": {"location": "Texas"}}]}],
            }
        ]

    def get_summary(self, event_id):
        self.summary_calls += 1
        if self.error:
            raise self.error
        return self.summary

    def get_summary_response(self, event_id):
        self.summary_calls += 1
        if self.error:
            raise self.error
        return ESPNProviderResponse(payload=self.summary, response_metadata=self.response_metadata)


def _summary_at(*, period: int, clock: str, pass_yards: int) -> dict:
    summary = deepcopy(espn_summary_payload())
    status = summary["header"]["competitions"][0]["status"]
    status["period"] = period
    status["displayClock"] = clock
    status["type"] = {"state": "in", "completed": False}
    summary["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["stats"][1] = str(pass_yards)
    return summary


def _final_summary(*, pass_yards: int) -> dict:
    summary = _summary_at(period=4, clock="00:00", pass_yards=pass_yards)
    summary["header"]["competitions"][0]["status"] = {"type": {"name": "STATUS_FINAL", "state": "post", "completed": True}}
    return summary


def _poll_due(db_session, *, at: datetime) -> ProviderGamePoll:
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    poll.next_poll_at = at
    db_session.commit()
    return poll


def _run_summary(db_session, *, summary: dict, at: datetime, mode: str = "shadow", response_metadata=None):
    _poll_due(db_session, at=at)
    return run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode=mode,
        client=FakeLiveESPN(summary=summary, response_metadata=response_metadata),
        now=at,
        relevant_team_names={"texas"},
    )


def _accepted_pass_yards(db_session) -> float:
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    snapshot = (
        db_session.query(ProviderGameSnapshot)
        .filter_by(provider_game_id="401", snapshot_hash=poll.accepted_snapshot_hash)
        .order_by(ProviderGameSnapshot.id.desc())
        .one()
    )
    return next(row["stats"]["pass_yards"] for row in snapshot.normalized_rows if row["player_id"])


def _verified_players(db_session):
    arch = Player(name="Arch Manning", position="QB", school="Texas")
    wingo = Player(name="Ryan Wingo", position="WR", school="Texas")
    db_session.add_all([arch, wingo])
    db_session.flush()
    db_session.add_all(
        [
            PlayerProviderId(player_id=arch.id, provider="espn", provider_player_id="101", verification_status="verified"),
            PlayerProviderId(player_id=wingo.id, provider="espn", provider_player_id="202", verification_status="verified"),
        ]
    )
    db_session.commit()
    return arch, wingo


def _make_public_promotion_ready(db_session, *, at):
    """Model the verified schedule + worker heartbeat required in production."""

    if db_session.query(Game).filter_by(external_id="401", season=2026, week=1).one_or_none() is None:
        db_session.add(Game(external_id="401", season=2026, week=1, home_team="Texas", away_team="Ohio State", start_date=NOW))
    heartbeat = db_session.query(WorkerHeartbeat).filter_by(worker_name="espn_scoring_processor").one_or_none()
    if heartbeat is None:
        heartbeat = WorkerHeartbeat(worker_name="espn_scoring_processor")
        db_session.add(heartbeat)
    heartbeat.status = "healthy"
    heartbeat.heartbeat_at = at
    db_session.commit()


def test_espn_status_names_with_the_provider_prefix_are_classified_as_live():
    assert _event_status({"status": {"type": {"name": "STATUS_IN_PROGRESS"}}}) == "live"
    assert _event_status({"status": {"type": {"name": "STATUS_FINAL", "completed": True}}}) == "final"


def test_resolve_scoring_window_prefers_the_complete_current_week_when_stale_week_rows_tie(db_session):
    """A duplicate prior-week row must not starve the actual live week."""

    kickoff = datetime(2026, 8, 29, 19, 30, tzinfo=timezone.utc)
    db_session.add_all(
        [
            TeamSchedule(team_name="North Carolina", season=2026, week=0, opponent_name="TCU", location="home", is_bye=False, kickoff_at=datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)),
            TeamSchedule(team_name="NC State", season=2026, week=0, opponent_name="Virginia", location="home", is_bye=False, kickoff_at=kickoff),
            TeamSchedule(team_name="Virginia", season=2026, week=0, opponent_name="NC State", location="away", is_bye=False, kickoff_at=kickoff),
            TeamSchedule(team_name="North Carolina", season=2026, week=1, opponent_name="TCU", location="home", is_bye=False, kickoff_at=datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)),
            TeamSchedule(team_name="TCU", season=2026, week=1, opponent_name="North Carolina", location="away", is_bye=False, kickoff_at=datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)),
            TeamSchedule(team_name="USC", season=2026, week=1, opponent_name="San José State", location="home", is_bye=False, kickoff_at=datetime(2026, 8, 29, 19, 0, tzinfo=timezone.utc)),
            TeamSchedule(team_name="NC State", season=2026, week=1, opponent_name="Virginia", location="home", is_bye=False, kickoff_at=kickoff),
            TeamSchedule(team_name="Virginia", season=2026, week=1, opponent_name="NC State", location="away", is_bye=False, kickoff_at=kickoff),
        ]
    )
    db_session.commit()

    assert scoring_worker.resolve_scoring_window(db_session, now=datetime(2026, 8, 29, 20, 13, tzinfo=timezone.utc)) == (2026, 1)


def test_scheduled_games_are_not_claimed_before_espn_publishes_box_scores(db_session):
    db_session.add(
        ProviderGamePoll(
            provider="espn",
            provider_game_id="pregame-event",
            season=2026,
            week=1,
            status="scheduled",
            next_poll_at=NOW,
        )
    )
    db_session.commit()

    assert claim_due_espn_games(db_session, season=2026, week=1, now=NOW) == []


def _synthetic_live_matchup(db_session, *, at):
    """Create an in-memory-only league used by the three-minute drill."""

    arch, wingo = _verified_players(db_session)
    _make_public_promotion_ready(db_session, at=at)
    game = db_session.query(Game).filter_by(external_id="401", season=2026, week=1).one()
    league = League(name="Synthetic live-scoring drill", season_year=2026, max_teams=2, status="post_draft")
    db_session.add(league)
    db_session.flush()
    home = Team(league_id=league.id, name="Synthetic Home")
    away = Team(league_id=league.id, name="Synthetic Away")
    db_session.add_all([home, away])
    db_session.flush()
    db_session.add_all(
        [
            LeagueSettings(
                league_id=league.id,
                scoring_json={"pass_yards": 0.04, "pass_tds": 4, "receptions": 1},
                roster_slots_json={"QB": 1, "WR": 1, "BENCH": 2},
            ),
            RosterEntry(league_id=league.id, team_id=home.id, player_id=arch.id, slot="QB", status="active"),
            RosterEntry(league_id=league.id, team_id=away.id, player_id=wingo.id, slot="WR", status="active"),
            Matchup(
                league_id=league.id,
                season=2026,
                week=1,
                home_team_id=home.id,
                away_team_id=away.id,
                status="scheduled",
            ),
            TeamSchedule(
                team_name="Texas",
                season=2026,
                week=1,
                game_id=game.id,
                opponent_name="Ohio State",
                location="home",
                is_bye=False,
                kickoff_at=at,
                neutral_site=False,
                conference_game=False,
                date_confirmed=True,
            ),
            TeamSchedule(
                team_name="Texas",
                season=2026,
                week=2,
                opponent_name="Next Opponent",
                location="away",
                is_bye=False,
                neutral_site=False,
                conference_game=False,
                date_confirmed=True,
            ),
        ]
    )
    db_session.commit()
    return league, arch, wingo


def test_shadow_cycle_uses_one_per_game_lease_and_never_promotes_public_scores(db_session):
    _verified_players(db_session)
    client = FakeLiveESPN()

    first = run_espn_scoring_cycle(
        db_session, season=2026, week=1, mode="shadow", client=client, worker_id="worker-a", now=NOW, relevant_team_names={"texas"}
    )
    second = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=client,
        worker_id="worker-b",
        now=NOW + timedelta(seconds=30),
        relevant_team_names={"texas"},
    )

    assert first.discovered_games == first.claimed_games == first.successful_games == 1
    assert first.normalized_rows == 2
    assert first.unmatched_rows == 1
    assert first.promoted_rows == 0
    assert second.claimed_games == 0
    assert client.summary_calls == 1
    assert db_session.query(PlayerStat).count() == 0
    assert db_session.query(ProviderGameSnapshot).count() == 1
    poll = db_session.query(ProviderGamePoll).filter_by(provider="espn", provider_game_id="401").one()
    assert _utc(poll.next_poll_at) >= NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS)
    assert db_session.query(UnmatchedProviderRow).filter_by(feed="live_boxscore_player_stats").count() == 1


def test_enabled_cycle_fails_closed_before_public_promotion_when_preflight_is_not_ready(db_session):
    _verified_players(db_session)

    with pytest.raises(PublicScoringPreflightError, match="SCORING_WORKER_UNHEALTHY"):
        run_espn_scoring_cycle(
            db_session, season=2026, week=1, mode="enabled", client=FakeLiveESPN(), now=NOW, relevant_team_names={"texas"}
        )

    assert db_session.query(PlayerStat).count() == 0


def test_synthetic_three_minute_drill_updates_matchup_then_finalizes_downstream_outlook(db_session):
    """Exercise the production pipeline with disposable fake ESPN payloads.

    The test database is torn down by the test fixture, so none of the fake
    game, player stats, matchup points, projections, or values can reach a
    real league.
    """

    league, arch, _wingo = _synthetic_live_matchup(db_session, at=NOW)

    first = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="enabled",
        client=FakeLiveESPN(summary=_summary_at(period=1, clock="10:00", pass_yards=80)),
        now=NOW,
        relevant_team_names={"texas"},
    )
    assert first.promoted_rows == 2
    first_score = db_session.query(PlayerWeekScore).filter_by(
        league_id=league.id, player_id=arch.id, season=2026, week=1
    ).one().fantasy_points
    assert db_session.query(WeeklyProjection).filter_by(season=2026, week=2).count() == 0

    _make_public_promotion_ready(db_session, at=NOW + timedelta(seconds=180))
    second = _run_summary(
        db_session,
        summary=_summary_at(period=2, clock="12:00", pass_yards=180),
        at=NOW + timedelta(seconds=180),
        mode="enabled",
    )
    assert second.promoted_rows == 2
    second_score = db_session.query(PlayerWeekScore).filter_by(
        league_id=league.id, player_id=arch.id, season=2026, week=1
    ).one().fantasy_points
    assert second_score > first_score
    assert db_session.query(Matchup).filter_by(league_id=league.id, season=2026, week=1).one().status == "live"

    _make_public_promotion_ready(db_session, at=NOW + timedelta(seconds=360))
    final = _run_summary(
        db_session,
        summary=_final_summary(pass_yards=300),
        at=NOW + timedelta(seconds=360),
        mode="enabled",
    )
    assert final.promoted_rows == 2
    matchup = db_session.query(Matchup).filter_by(league_id=league.id, season=2026, week=1).one()
    assert matchup.status == "final"
    assert matchup.home_score > second_score
    game = db_session.query(Game).filter_by(external_id="401", season=2026, week=1).one()
    assert (game.home_points, game.away_points, game.schedule_status) == (31, 24, "final")
    final_box_score = db_session.query(PlayerGameStat).filter_by(player_id=arch.id, game_id=game.id).one()
    assert final_box_score.source == "espn_final_boxscore"
    assert final_box_score.stats["pass_yards"] == 300.0
    assert db_session.query(WeeklyProjection).filter_by(
        player_id=arch.id,
        season=2026,
        week=2,
        projection_version="MIDWEEK",
    ).count() == 1


def test_recorded_replay_runs_through_worker_entrypoint_and_survives_restart(db_session, monkeypatch):
    """Exercise the real worker entrypoint with deterministic ESPN snapshots.

    The alpha workflow runs this suite against disposable PostgreSQL.  The
    test replaces only the external HTTP adapter with recorded payloads; all
    schedule resolution, durable poll leases, snapshot persistence, scoring,
    finality, worker heartbeats, and downstream outlook work stay on the
    actual worker path.
    """

    league, arch, _wingo = _synthetic_live_matchup(db_session, at=NOW)
    league_id = league.id
    arch_id = arch.id
    worker_sessions = sessionmaker(bind=db_session.get_bind(), autocommit=False, autoflush=False)
    monkeypatch.setattr(scoring_worker, "SessionLocal", worker_sessions)
    monkeypatch.setattr(settings, "scoring_mode", "enabled")
    monkeypatch.setattr(settings, "scoring_provider", "espn")

    first = scoring_worker.run_iteration(
        now=NOW,
        client=FakeLiveESPN(summary=_summary_at(period=1, clock="10:00", pass_yards=80)),
    )
    assert first is not None
    assert first.promoted_rows == 2

    # Simulate a process restart: run_iteration opens a fresh session and must
    # resume from persisted poll/snapshot state rather than in-memory state.
    _make_public_promotion_ready(db_session, at=NOW + timedelta(seconds=180))
    _poll_due(db_session, at=NOW + timedelta(seconds=180))
    db_session.expunge_all()
    second = scoring_worker.run_iteration(
        now=NOW + timedelta(seconds=180),
        client=FakeLiveESPN(summary=_summary_at(period=2, clock="12:00", pass_yards=180)),
    )
    assert second is not None
    assert second.promoted_rows == 2

    _make_public_promotion_ready(db_session, at=NOW + timedelta(seconds=360))
    _poll_due(db_session, at=NOW + timedelta(seconds=360))
    final = scoring_worker.run_iteration(
        now=NOW + timedelta(seconds=360),
        client=FakeLiveESPN(summary=_final_summary(pass_yards=300)),
    )
    assert final is not None
    assert final.promoted_rows == 2

    # A replayed final payload is persisted for auditability but cannot score
    # the player or finalize the matchup a second time.
    _poll_due(db_session, at=NOW + timedelta(seconds=540))
    duplicate = scoring_worker.run_iteration(
        now=NOW + timedelta(seconds=540),
        client=FakeLiveESPN(summary=_final_summary(pass_yards=300)),
    )
    assert duplicate is not None
    assert duplicate.promoted_rows == 0

    db_session.expire_all()
    matchup = db_session.query(Matchup).filter_by(league_id=league_id, season=2026, week=1).one()
    score = db_session.query(PlayerWeekScore).filter_by(
        league_id=league_id,
        player_id=arch_id,
        season=2026,
        week=1,
    ).one()
    heartbeat = db_session.query(WorkerHeartbeat).filter_by(worker_name="espn_scoring_processor").one()
    assert matchup.status == "final"
    assert score.fantasy_points == 31.4
    assert heartbeat.status == "healthy"
    assert db_session.query(WeeklyProjection).filter_by(
        player_id=arch_id,
        season=2026,
        week=2,
        projection_version="MIDWEEK",
    ).count() == 1


def test_accepted_snapshot_queues_only_new_verified_long_play_alerts(db_session, monkeypatch):
    arch, wingo = _verified_players(db_session)
    user = User(
        email="long-play-owner@example.com",
        first_name="Long Play",
        password_hash="test-hash",
        api_token="long-play-owner-token",
    )
    league = League(name="Long Play League", season_year=2026)
    db_session.add_all([user, league])
    db_session.flush()
    team = Team(league_id=league.id, name="Owner Team", owner_user_id=user.id)
    db_session.add(team)
    db_session.flush()
    db_session.add_all(
        [
            RosterEntry(league_id=league.id, team_id=team.id, player_id=arch.id, slot="QB", status="active"),
            RosterEntry(league_id=league.id, team_id=team.id, player_id=wingo.id, slot="WR", status="active"),
        ]
    )
    prior_payload = espn_summary_payload()
    previous = ProviderGameSnapshot(
        provider="espn",
        provider_game_id="401",
        season=2026,
        week=1,
        status="live",
        captured_at=NOW,
        snapshot_hash="prior-snapshot",
        raw_payload=prior_payload,
        normalized_rows=[],
        accepted=True,
    )
    current_payload = deepcopy(prior_payload)
    current_payload["drives"]["previous"].append(
        {
            "plays": [
                {
                    "id": "long-pass-1",
                    "type": {"text": "Pass"},
                    "text": "Arch Manning pass complete to Ryan Wingo for 48 yds",
                    "statYardage": 48,
                }
            ]
        }
    )
    db_session.add(previous)
    db_session.commit()
    monkeypatch.setattr(settings, "live_player_notifications_enabled", True)

    queued = queue_accepted_espn_long_play_notifications(
        db_session,
        provider_game_id="401",
        summary=current_payload,
        previous_snapshot=previous,
    )
    db_session.commit()

    assert queued == 2
    assert {row.event_type for row in db_session.query(ScheduledNotification).all()} == {"LONG_PASS", "LONG_RECEPTION"}
    assert queue_accepted_espn_long_play_notifications(
        db_session,
        provider_game_id="401",
        summary=current_payload,
        previous_snapshot=previous,
    ) == 0


def test_100_league_1000_roster_cache_is_per_game_not_per_roster_or_read(db_session):
    """A shared college game remains one provider request per 180-second window."""

    players = [Player(name=f"Shared Texas Player {index}", position="WR", school="Texas") for index in range(10)]
    db_session.add_all(players)
    db_session.flush()
    for league_index in range(100):
        league = League(name=f"ESPN scale {league_index}", season_year=2026, max_teams=1)
        db_session.add(league)
        db_session.flush()
        team = Team(league_id=league.id, name=f"Scale team {league_index}")
        db_session.add(team)
        db_session.flush()
        db_session.add_all(
            RosterEntry(
                league_id=league.id,
                team_id=team.id,
                player_id=player.id,
                slot="BE",
                status="active",
            )
            for player in players
        )
    db_session.commit()

    assert db_session.query(League).count() == 100
    assert db_session.query(RosterEntry).count() == 1000
    client = FakeLiveESPN()
    first = run_espn_scoring_cycle(db_session, season=2026, week=1, mode="shadow", client=client, worker_id="worker-a", now=NOW)
    assert first.successful_games == 1
    assert client.summary_calls == 1

    # These model repeated UI/API freshness reads. Only the worker owns
    # provider traffic, so no number of manager reads can fetch ESPN.
    for offset in (30, 60, 90, 120, 150, 179):
        for _ in range(100):
            espn_week_freshness(db_session, season=2026, week=1, now=NOW + timedelta(seconds=offset))
        result = run_espn_scoring_cycle(
            db_session,
            season=2026,
            week=1,
            mode="shadow",
            client=client,
            worker_id=f"worker-before-{offset}",
            now=NOW + timedelta(seconds=offset),
        )
        assert result.claimed_games == 0
        assert client.summary_calls == 1

    at_boundary = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=client,
        worker_id="worker-b",
        now=NOW + timedelta(seconds=180),
    )
    assert at_boundary.successful_games == 1
    assert client.summary_calls == 2
    # Discovery is durable/per-week as well: one initial request and one
    # permitted boundary refresh, never one per league or browser read.
    assert client.scoreboard_calls == 2


def test_shadow_mode_cannot_change_existing_public_score_authority(db_session):
    league, _home, _away, _players, matchup = create_scoring_fixture(db_session)
    before_stats = db_session.query(PlayerStat).count()
    before_player_scores = db_session.query(PlayerWeekScore).count()
    before_team_scores = db_session.query(TeamWeekScore).count()
    before_status = matchup.status

    result = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(),
        now=NOW,
        relevant_team_names={"texas"},
    )

    assert result.promoted_rows == 0
    assert db_session.query(PlayerStat).count() == before_stats
    assert db_session.query(PlayerWeekScore).count() == before_player_scores
    assert db_session.query(TeamWeekScore).count() == before_team_scores
    assert db_session.get(Matchup, matchup.id).status == before_status
    assert db_session.query(ProviderGameSnapshot).count() == 1


def test_strict_live_identity_never_uses_external_or_name_school_fallback(db_session):
    db_session.add(Player(name="Arch Manning", position="QB", school="Texas", external_id="espn:101"))
    db_session.commit()
    result = run_espn_scoring_cycle(
        db_session, season=2026, week=1, mode="shadow", client=FakeLiveESPN(), now=NOW, relevant_team_names={"texas"}
    )

    assert result.normalized_rows == 0
    assert result.unmatched_rows == 3
    assert db_session.query(ProviderGameSnapshot).one().normalized_rows == []


def test_strict_live_identity_rejects_legacy_backfill_mappings(db_session):
    player = Player(name="Arch Manning", position="QB", school="Texas")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        PlayerProviderId(
            player_id=player.id,
            provider="espn",
            provider_player_id="101",
            verification_status="legacy_backfill",
        )
    )
    db_session.commit()

    result = run_espn_scoring_cycle(
        db_session, season=2026, week=1, mode="shadow", client=FakeLiveESPN(), now=NOW, relevant_team_names={"texas"}
    )

    assert result.normalized_rows == 0
    assert result.unmatched_rows == 3


def test_verified_unrostered_kicker_with_unbucketed_made_field_goal_does_not_block_other_players(db_session):
    _verified_players(db_session)
    kicker = Player(name="Exact Distance Kicker", position="K", school="Texas")
    db_session.add(kicker)
    db_session.flush()
    db_session.add(PlayerProviderId(player_id=kicker.id, provider="espn", provider_player_id="303", verification_status="verified"))
    db_session.commit()

    summary = espn_summary_payload()
    summary.pop("drives")
    normalized, skipped = normalize_espn_summary_player_stats(db_session, season=2026, week=1, summary=summary, strict_identity=True)
    assert skipped == 1
    assert kicker.id not in {row["player_id"] for row in normalized}

    result = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(summary=summary),
        now=NOW,
        relevant_team_names={"texas"},
    )
    assert result.successful_games == 1
    assert result.failed_games == 0
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.status == "live"
    assert db_session.query(UnmatchedProviderRow).filter_by(feed="live_boxscore_kicker_distance").count() == 1


def test_verified_rostered_kicker_with_unbucketed_made_field_goal_delays_the_game_without_promoting_stats(db_session):
    league, home, _away, _players, _matchup = create_scoring_fixture(db_session)
    kicker = Player(name="Exact Distance Kicker", position="K", school="Texas")
    db_session.add(kicker)
    db_session.flush()
    db_session.add_all(
        [
            PlayerProviderId(player_id=kicker.id, provider="espn", provider_player_id="303", verification_status="verified"),
            RosterEntry(league_id=league.id, team_id=home.id, player_id=kicker.id, slot="K", status="active"),
        ]
    )
    db_session.commit()

    summary = espn_summary_payload()
    summary.pop("drives")
    with pytest.raises(UnresolvedKickerDistanceError):
        normalize_espn_summary_player_stats(db_session, season=2026, week=1, summary=summary, strict_identity=True)

    result = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(summary=summary),
        now=NOW,
        relevant_team_names={"texas"},
    )
    assert result.failed_games == 1
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.status == "delayed"
    assert db_session.query(UnmatchedProviderRow).filter_by(feed="live_boxscore_kicker_distance").count() == 1


def test_final_snapshot_can_omit_an_unrostered_kicker_without_blocking_active_players(db_session):
    _verified_players(db_session)
    kicker = Player(name="Exact Distance Kicker", position="K", school="Texas")
    db_session.add(kicker)
    db_session.flush()
    db_session.add(PlayerProviderId(player_id=kicker.id, provider="espn", provider_player_id="303", verification_status="verified"))
    db_session.commit()

    live_summary = espn_summary_payload()
    first = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(summary=live_summary),
        now=NOW,
        relevant_team_names={"texas"},
    )
    assert first.successful_games == 1
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    poll.next_poll_at = NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS)
    db_session.commit()

    final_summary = _final_summary(pass_yards=180)
    final_summary.pop("drives")
    second = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(summary=final_summary),
        now=NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS),
        relevant_team_names={"texas"},
    )

    assert second.successful_games == 1
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.status == "final"
    accepted = db_session.query(ProviderGameSnapshot).filter_by(provider_game_id="401", accepted=True).order_by(ProviderGameSnapshot.id.desc()).first()
    assert accepted is not None
    assert accepted.event_state == "final"
    assert kicker.id not in {row["player_id"] for row in accepted.normalized_rows}


def test_identical_replay_is_audited_without_promoting_and_later_progress_replaces_cumulative_totals(db_session):
    arch, _wingo = _verified_players(db_session)
    client = FakeLiveESPN()
    run_espn_scoring_cycle(db_session, season=2026, week=1, mode="shadow", client=client, now=NOW, relevant_team_names={"texas"})
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    poll.next_poll_at = NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS)
    db_session.commit()
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=client,
        now=NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS),
        relevant_team_names={"texas"},
    )
    assert db_session.query(ProviderGameSnapshot).count() == 2
    assert poll.duplicate_snapshot_count == 1

    updated = espn_summary_payload()
    updated["header"]["competitions"][0]["status"]["displayClock"] = "09:00"
    updated["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["stats"][1] = "300"
    poll.next_poll_at = NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS * 2)
    db_session.commit()
    _make_public_promotion_ready(db_session, at=NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS * 2))
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="enabled",
        client=FakeLiveESPN(summary=updated),
        now=NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS * 2),
        relevant_team_names={"texas"},
    )
    stat = db_session.query(PlayerStat).filter_by(player_id=arch.id, season=2026, week=1).one()
    assert stat.stats["pass_yards"] == 300.0
    assert db_session.query(ProviderGameSnapshot).count() == 3


def test_snapshot_ordering_keeps_the_latest_accepted_live_state_on_stale_and_ambiguous_payloads(db_session):
    _verified_players(db_session)
    first = _summary_at(period=1, clock="10:00", pass_yards=80)
    run_espn_scoring_cycle(
        db_session, season=2026, week=1, mode="shadow", client=FakeLiveESPN(summary=first), now=NOW, relevant_team_names={"texas"}
    )
    assert _accepted_pass_yards(db_session) == 80.0

    later = _summary_at(period=1, clock="07:00", pass_yards=180)
    _run_summary(db_session, summary=later, at=NOW + timedelta(seconds=180))
    assert _accepted_pass_yards(db_session) == 180.0

    next_period = _summary_at(period=2, clock="12:00", pass_yards=220)
    _run_summary(db_session, summary=next_period, at=NOW + timedelta(seconds=360))
    assert _accepted_pass_yards(db_session) == 220.0

    stale = _summary_at(period=1, clock="10:00", pass_yards=80)
    _run_summary(db_session, summary=stale, at=NOW + timedelta(seconds=540))
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.last_snapshot_classification == "STALE"
    assert poll.stale_snapshot_count == 1
    assert _accepted_pass_yards(db_session) == 220.0

    ambiguous = _summary_at(period=2, clock="12:00", pass_yards=217)
    _run_summary(db_session, summary=ambiguous, at=NOW + timedelta(seconds=720))
    db_session.refresh(poll)
    assert poll.last_snapshot_classification == "AMBIGUOUS"
    assert poll.ambiguous_snapshot_count == 1
    assert _accepted_pass_yards(db_session) == 220.0


def test_later_live_progress_can_accept_a_legitimate_stat_decrease(db_session):
    _verified_players(db_session)
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(summary=_summary_at(period=2, clock="08:00", pass_yards=150)),
        now=NOW,
        relevant_team_names={"texas"},
    )
    _run_summary(
        db_session,
        summary=_summary_at(period=2, clock="04:00", pass_yards=147),
        at=NOW + timedelta(seconds=180),
    )
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.last_snapshot_classification == "NEWER"
    assert _accepted_pass_yards(db_session) == 147.0


def test_final_state_is_immutable_without_a_newer_authoritative_revision(db_session):
    _verified_players(db_session)
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(summary=_final_summary(pass_yards=300)),
        now=NOW,
        relevant_team_names={"texas"},
    )
    _run_summary(
        db_session,
        summary=_summary_at(period=4, clock="02:00", pass_yards=280),
        at=NOW + timedelta(seconds=180),
    )
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.last_snapshot_classification == "STALE"
    assert poll.status == "final"
    assert _accepted_pass_yards(db_session) == 300.0

    _run_summary(
        db_session,
        summary=_final_summary(pass_yards=294),
        at=NOW + timedelta(seconds=360),
    )
    db_session.refresh(poll)
    assert poll.last_snapshot_classification == "AMBIGUOUS"
    assert poll.pending_final_correction_count == 1
    assert _accepted_pass_yards(db_session) == 300.0


def test_final_correction_requires_a_monotonic_provider_revision_and_promotes_once(db_session):
    arch, _wingo = _verified_players(db_session)
    _make_public_promotion_ready(db_session, at=NOW)
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="enabled",
        client=FakeLiveESPN(summary=_final_summary(pass_yards=300), response_metadata={"provider_revision": "10"}),
        now=NOW,
        relevant_team_names={"texas"},
    )
    _make_public_promotion_ready(db_session, at=NOW + timedelta(seconds=180))
    _run_summary(
        db_session,
        summary=_final_summary(pass_yards=294),
        at=NOW + timedelta(seconds=180),
        mode="enabled",
        response_metadata={"provider_revision": "11"},
    )
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.last_snapshot_classification == "VERIFIED_CORRECTION"
    assert db_session.query(PlayerStat).filter_by(player_id=arch.id, season=2026, week=1).one().stats["pass_yards"] == 294.0


def test_enabled_worker_backfills_previously_accepted_final_box_scores(db_session):
    """A deployment can safely populate completed games without refetching ESPN."""

    _league, arch, _wingo = _synthetic_live_matchup(db_session, at=NOW)
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(summary=_final_summary(pass_yards=300)),
        now=NOW,
        relevant_team_names={"texas"},
    )
    assert db_session.query(PlayerGameStat).filter_by(player_id=arch.id).count() == 0

    _make_public_promotion_ready(db_session, at=NOW + timedelta(seconds=180))
    result = _run_summary(
        db_session,
        summary=_final_summary(pass_yards=300),
        at=NOW + timedelta(seconds=180),
        mode="enabled",
    )

    assert result.promoted_rows == 0  # Duplicate provider snapshot.
    final_box_score = db_session.query(PlayerGameStat).filter_by(player_id=arch.id).one()
    assert final_box_score.source == "espn_final_boxscore"
    assert final_box_score.stats["pass_yards"] == 300.0


def test_snapshot_ordering_survives_a_worker_restart_and_two_claimers(db_session):
    _verified_players(db_session)
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(summary=_summary_at(period=3, clock="07:00", pass_yards=295)),
        now=NOW,
        relevant_team_names={"texas"},
        worker_id="first-process",
    )
    db_session.expunge_all()  # A new process/session must rely on persisted state only.
    _run_summary(
        db_session,
        summary=_summary_at(period=2, clock="05:00", pass_yards=180),
        at=NOW + timedelta(seconds=180),
    )
    assert _accepted_pass_yards(db_session) == 295.0
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.last_snapshot_classification == "STALE"

    poll.next_poll_at = NOW + timedelta(seconds=360)
    db_session.commit()
    first = claim_due_espn_games(db_session, season=2026, week=1, worker_id="worker-a", now=NOW + timedelta(seconds=360))
    second = claim_due_espn_games(db_session, season=2026, week=1, worker_id="worker-b", now=NOW + timedelta(seconds=360))
    assert len(first) == 1
    assert second == []


def test_snapshot_classifier_requires_explicit_strong_revision_for_final_correction():
    previous = ProviderGameSnapshot(
        provider="espn",
        provider_game_id="401",
        season=2026,
        week=1,
        status="final",
        snapshot_hash="a" * 64,
        captured_at=NOW,
        provider_revision="10",
        event_state="final",
        raw_payload={},
        normalized_rows=[],
    )
    decision = classify_snapshot_order(
        previous,
        candidate_hash="b" * 64,
        candidate=SnapshotOrderMetadata("11", None, None, {}, None, None, "final"),
    )
    assert decision.classification == "VERIFIED_CORRECTION"
    assert decision.accepted is True


def test_429_and_403_enter_backoff_without_clearing_verified_data(db_session):
    _verified_players(db_session)
    response_429 = httpx.Response(429, headers={"Retry-After": "300"}, request=httpx.Request("GET", "https://espn.test"))
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(error=httpx.HTTPStatusError("rate limited", request=response_429.request, response=response_429)),
        now=NOW,
        relevant_team_names={"texas"},
    )
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.status == "delayed"
    assert _utc(poll.next_poll_at) >= NOW + timedelta(seconds=300)

    poll.next_poll_at = NOW + timedelta(seconds=301)
    db_session.commit()
    response_403 = httpx.Response(403, request=httpx.Request("GET", "https://espn.test"))
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(error=httpx.HTTPStatusError("forbidden", request=response_403.request, response=response_403)),
        now=NOW + timedelta(seconds=301),
        relevant_team_names={"texas"},
    )
    db_session.refresh(poll)
    assert poll.status == "blocked"
    assert _utc(poll.next_poll_at) > NOW + timedelta(hours=1)


def test_timeout_marks_only_the_game_poll_delayed_and_does_not_retry_immediately(db_session):
    _verified_players(db_session)
    run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="shadow",
        client=FakeLiveESPN(error=httpx.TimeoutException("provider timeout")),
        now=NOW,
        relevant_team_names={"texas"},
    )
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    assert poll.status == "delayed"
    assert _utc(poll.next_poll_at) >= NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS)


def test_incomplete_provider_data_retries_at_the_next_live_poll_without_exponential_delay():
    for failure_count in range(1, 8):
        status, retry_seconds = _failure_policy(
            ProviderDataIncompleteError("summary is temporarily incomplete"),
            failure_count=failure_count,
        )
        assert status == "delayed"
        assert retry_seconds == MIN_GAME_POLL_INTERVAL_SECONDS


def test_transient_provider_failures_have_a_bounded_retry_delay():
    status, retry_seconds = _failure_policy(RuntimeError("temporary provider parsing failure"), failure_count=20)

    assert status == "delayed"
    assert retry_seconds == MAX_TRANSIENT_GAME_RETRY_SECONDS


def test_empty_or_partial_summary_preserves_last_verified_cumulative_totals(db_session):
    arch, wingo = _verified_players(db_session)
    client = FakeLiveESPN()
    _make_public_promotion_ready(db_session, at=NOW)
    run_espn_scoring_cycle(
        db_session, season=2026, week=1, mode="enabled", client=client, now=NOW, relevant_team_names={"texas"}
    )
    first_arch = db_session.query(PlayerStat).filter_by(player_id=arch.id, season=2026, week=1).one().stats["pass_yards"]
    first_wingo = db_session.query(PlayerStat).filter_by(player_id=wingo.id, season=2026, week=1).one().stats["rec_yards"]
    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()

    poll.next_poll_at = NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS)
    db_session.commit()
    empty = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="enabled",
        client=FakeLiveESPN(summary={"boxscore": {"players": []}}),
        now=NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS),
        relevant_team_names={"texas"},
    )
    assert empty.failed_games == 1
    db_session.refresh(poll)
    assert poll.status == "delayed"
    assert db_session.query(PlayerStat).filter_by(player_id=arch.id, season=2026, week=1).one().stats["pass_yards"] == first_arch

    partial_summary = deepcopy(espn_summary_payload())
    partial_summary["boxscore"]["players"][0]["statistics"][2]["athletes"] = []
    partial_summary["boxscore"]["players"][0]["statistics"][3]["athletes"] = []
    poll.next_poll_at = NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS * 2)
    db_session.commit()
    partial = run_espn_scoring_cycle(
        db_session,
        season=2026,
        week=1,
        mode="enabled",
        client=FakeLiveESPN(summary=partial_summary),
        now=NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS * 2),
        relevant_team_names={"texas"},
    )
    assert partial.failed_games == 1
    assert db_session.query(PlayerStat).filter_by(player_id=wingo.id, season=2026, week=1).one().stats["rec_yards"] == first_wingo


def test_two_claimers_cannot_claim_the_same_due_game(db_session):
    discover_relevant_espn_games(
        db_session,
        season=2026,
        week=1,
        events=[{"id": "401", "status": {"type": {"state": "in"}}}],
        now=NOW,
    )
    db_session.commit()

    first = claim_due_espn_games(db_session, season=2026, week=1, worker_id="one", now=NOW)
    second = claim_due_espn_games(db_session, season=2026, week=1, worker_id="two", now=NOW)

    assert [item.provider_game_id for item in first] == ["401"]
    assert second == []


def test_week_freshness_is_explicit_when_provider_is_unavailable_delayed_or_stale(db_session):
    unavailable = espn_week_freshness(db_session, season=2026, week=1, now=NOW)
    assert unavailable.state == "unavailable"
    assert unavailable.provider is None

    delayed = ProviderGamePoll(
        provider="espn",
        provider_game_id="401",
        season=2026,
        week=1,
        status="delayed",
    )
    db_session.add(delayed)
    db_session.commit()
    assert espn_week_freshness(db_session, season=2026, week=1, now=NOW).state == "delayed"

    delayed.status = "live"
    delayed.last_success_at = NOW - timedelta(minutes=7)
    delayed.provider_as_of = delayed.last_success_at
    db_session.commit()
    freshness = espn_week_freshness(db_session, season=2026, week=1, now=NOW)
    assert freshness.state == "stale"
    assert freshness.data_age_seconds == 420


def test_finality_requires_explicit_final_espn_status_for_every_starter_and_marks_corrections(db_session):
    league, home, away, players, matchup = create_scoring_fixture(db_session)
    db_session.add(Game(external_id="401", season=2026, week=1, home_team="Test", away_team="Other", schedule_status="final"))
    for team_id, player_id in (
        (home.id, players["qb"].id),
        (home.id, players["rb"].id),
        (home.id, players["wr"].id),
        (away.id, players["away_qb"].id),
    ):
        db_session.add(
            LineupWeekSnapshot(
                league_id=league.id,
                team_id=team_id,
                player_id=player_id,
                season=2026,
                week=1,
                slot="QB",
                is_starter=True,
            )
        )
    db_session.add(ProviderGamePoll(provider="espn", provider_game_id="401", season=2026, week=1, status="live"))
    db_session.commit()

    assert certify_espn_matchup_finality(db_session, season=2026, week=1) == 0
    assert db_session.get(Matchup, matchup.id).status == "scheduled"

    poll = db_session.query(ProviderGamePoll).filter_by(provider_game_id="401").one()
    poll.status = "final"
    db_session.commit()
    assert certify_espn_matchup_finality(db_session, season=2026, week=1) == 1
    assert db_session.get(Matchup, matchup.id).status == "final"

    assert certify_espn_matchup_finality(
        db_session,
        season=2026,
        week=1,
        corrected_provider_game_ids={"401"},
    ) == 1
    assert db_session.get(Matchup, matchup.id).status == "stat_corrected"
