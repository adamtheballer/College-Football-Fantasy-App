from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll, ProviderGameSnapshot
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId, UnmatchedProviderRow
from collegefootballfantasy_api.app.services.espn_live_scoring import (
    MIN_GAME_POLL_INTERVAL_SECONDS,
    claim_due_espn_games,
    discover_relevant_espn_games,
    certify_espn_matchup_finality,
    espn_week_freshness,
    run_espn_scoring_cycle,
)
from tests.api.scoring_helpers import create_scoring_fixture
from tests.api.test_espn_boxscores import espn_summary_payload


NOW = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class FakeLiveESPN:
    def __init__(self, summary=None, error=None):
        self.summary = summary or espn_summary_payload()
        self.error = error
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


def test_strict_live_identity_never_uses_external_or_name_school_fallback(db_session):
    db_session.add(Player(name="Arch Manning", position="QB", school="Texas", external_id="espn:101"))
    db_session.commit()
    result = run_espn_scoring_cycle(
        db_session, season=2026, week=1, mode="shadow", client=FakeLiveESPN(), now=NOW, relevant_team_names={"texas"}
    )

    assert result.normalized_rows == 0
    assert result.unmatched_rows == 3
    assert db_session.query(ProviderGameSnapshot).one().normalized_rows == []


def test_identical_replay_creates_one_immutable_snapshot_and_enabled_mode_replaces_cumulative_totals(db_session):
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
    assert db_session.query(ProviderGameSnapshot).count() == 1

    updated = espn_summary_payload()
    updated["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["stats"][1] = "300"
    poll.next_poll_at = NOW + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS * 2)
    db_session.commit()
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
    assert db_session.query(ProviderGameSnapshot).count() == 2


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


def test_empty_or_partial_summary_preserves_last_verified_cumulative_totals(db_session):
    arch, wingo = _verified_players(db_session)
    client = FakeLiveESPN()
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
