from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.live_scoring_contract import FINAL_UNVERIFIED, IN_PROGRESS
from collegefootballfantasy_api.app.integrations.espn_live_scoring_adapter import (
    EspnAthleteStatLine,
    EspnGame,
    EspnGameSummary,
    EspnLiveProviderError,
    EspnLiveScoringAdapter,
)
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.live_scoring import (
    PlayerGameStatRevision,
    ProviderGameIdentity,
    ProviderGamePollState,
    ProviderPollingHealth,
    ProviderRawEvent,
    ScoringCalculationSnapshot,
)
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId, UnmatchedProviderRow
from collegefootballfantasy_api.app.services.espn_live_polling_service import run_espn_shadow_poll_iteration
from collegefootballfantasy_api.app.services.live_scoring_service import (
    ensure_relevant_espn_poll_states,
    ingest_espn_game_summary,
    record_espn_poll_failure,
)
from tests.api.test_admin_scoring import auth_headers, create_user_and_token
from tests.api.scoring_helpers import create_scoring_fixture


def _espn_identity_ready(db_session):
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)
    game = Game(season=2026, week=1, season_type="regular", home_team="Test", away_team="Opponent")
    db_session.add(game)
    db_session.flush()
    db_session.add_all(
        [
            PlayerProviderId(
                player_id=players["qb"].id,
                provider="espn",
                provider_player_id="espn-qb-1",
                verification_status="verified",
            ),
            ProviderGameIdentity(
                provider="espn",
                provider_game_id="espn-game-1",
                game_id=game.id,
                verification_status="verified",
            ),
        ]
    )
    db_session.commit()
    return league, players["qb"], game


def _summary(*, pass_yards: int = 250, status: str = IN_PROGRESS, include_unknown: bool = False) -> EspnGameSummary:
    lines = [
        EspnAthleteStatLine(
            athlete_id="espn-qb-1",
            athlete_name="Exact QB",
            team_id="1",
            stats={"pass_yards": pass_yards, "pass_tds": 2, "interceptions": 1},
            completeness="complete",
        )
    ]
    if include_unknown:
        lines.append(
            EspnAthleteStatLine(
                athlete_id="unknown-espn-athlete",
                athlete_name="Same Name Is Not Enough",
                team_id="1",
                stats={"rush_yards": 100, "rush_tds": 1},
                completeness="complete",
            )
        )
    payload = {"event": "espn-game-1", "pass_yards": pass_yards, "status": status}
    return EspnGameSummary(
        game=EspnGame(
            game_id="espn-game-1",
            status=status,
            season=2026,
            week=1,
            start_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
            payload=payload,
        ),
        athlete_lines=tuple(lines),
        payload=payload,
    )


class _Response:
    def __init__(self, payload, status_code=200, headers=None, json_error=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, _url, params):
        assert params
        return self.responses.pop(0)


def test_espn_adapter_parses_structured_scoreboard_and_merges_athlete_categories():
    scoreboard = {
        "events": [
            {
                "id": "espn-game-1",
                "date": "2026-08-29T16:00Z",
                "status": {"type": {"state": "in", "name": "STATUS_IN_PROGRESS"}},
            }
        ]
    }
    summary = {
        "header": {"competitions": [{"date": "2026-08-29T16:00Z", "status": {"type": {"state": "in"}}}]},
        "boxscore": {
            "players": [
                {
                    "team": {"id": "1"},
                    "statistics": [
                        {"name": "passing", "names": ["C/ATT", "YDS", "TD", "INT"], "athletes": [{"athlete": {"id": "espn-qb-1"}, "stats": ["20/30", "250", "2", "1"]}]},
                        {"name": "rushing", "names": ["CAR", "YDS", "TD"], "athletes": [{"athlete": {"id": "espn-qb-1"}, "stats": ["8", "40", "1"]}]},
                        {"name": "kicking", "names": ["FG", "XP"], "athletes": [{"athlete": {"id": "espn-k-1"}, "stats": ["2/3", "3/3"]}]},
                    ],
                }
            ]
        },
    }
    adapter = EspnLiveScoringAdapter(base_url="https://example.invalid", client=_Client([_Response(scoreboard), _Response(summary)]))

    game = adapter.fetch_scoreboard(season=2026, week=1)[0]
    result = adapter.fetch_game_summary(game_id=game.game_id, season=2026, week=1)

    qb = next(line for line in result.athlete_lines if line.athlete_id == "espn-qb-1")
    assert game.status == IN_PROGRESS
    assert qb.stats == {"pass_yards": "250", "pass_tds": "2", "interceptions": "1", "pass_completions": 20, "pass_attempts": 30, "rush_yards": "40", "rush_tds": "1", "rush_attempts": "8"}
    kicker = next(line for line in result.athlete_lines if line.athlete_id == "espn-k-1")
    assert kicker.completeness == "incomplete"


def test_espn_adapter_stops_on_rate_limit_or_provider_block():
    adapter = EspnLiveScoringAdapter(base_url="https://example.invalid", client=_Client([_Response({}, status_code=429, headers={"Retry-After": "600"})]))
    with pytest.raises(EspnLiveProviderError) as limited:
        adapter.fetch_scoreboard(season=2026, week=1)
    assert limited.value.category == "RATE_LIMITED"
    assert limited.value.retry_after == 600

    blocked = EspnLiveScoringAdapter(base_url="https://example.invalid", client=_Client([_Response({}, status_code=403)]))
    with pytest.raises(EspnLiveProviderError) as denied:
        blocked.fetch_scoreboard(season=2026, week=1)
    assert denied.value.category == "PROVIDER_BLOCKED"


@pytest.mark.parametrize(
    ("response", "expected_category"),
    [
        (_Response({}, status_code=500), "PROVIDER_5XX"),
        (_Response({}, json_error=ValueError("bad json")), "INVALID_PAYLOAD"),
    ],
)
def test_espn_adapter_treats_server_errors_and_malformed_json_as_provider_failures(response, expected_category):
    adapter = EspnLiveScoringAdapter(base_url="https://example.invalid", client=_Client([response]))

    with pytest.raises(EspnLiveProviderError) as failure:
        adapter.fetch_scoreboard(season=2026, week=1)

    assert failure.value.category == expected_category


@pytest.mark.parametrize(
    ("provider_status", "expected_status"),
    [
        ({"type": {"state": "pre", "name": "STATUS_SCHEDULED"}}, "pre_game"),
        ({"type": {"state": "in", "name": "STATUS_HALFTIME"}}, "halftime"),
        ({"type": {"state": "in", "name": "STATUS_IN_PROGRESS"}}, "in_progress"),
        ({"type": {"state": "post", "completed": True}}, FINAL_UNVERIFIED),
        ({"type": {"state": "post", "description": "Postponed"}}, "postponed"),
        ({"type": {"state": "post", "description": "Cancelled"}}, "canceled"),
    ],
)
def test_espn_adapter_normalizes_game_lifecycle_statuses(provider_status, expected_status):
    adapter = EspnLiveScoringAdapter(
        base_url="https://example.invalid",
        client=_Client([_Response({"events": [{"id": "espn-game-1", "date": "2026-08-29T16:00Z", "status": provider_status}]})]),
    )

    result = adapter.fetch_scoreboard(season=2026, week=1)

    assert result[0].status == expected_status


def test_summary_uses_exact_identity_revisions_and_never_writes_public_player_stats(client, db_session):
    _league, qb, _game = _espn_identity_ready(db_session)
    assert ensure_relevant_espn_poll_states(db_session, season=2026, week=1) == 1
    state = db_session.query(ProviderGamePollState).one()
    public_stat_count = db_session.query(PlayerStat).count()

    first = ingest_espn_game_summary(db_session, state_id=state.id, summary=_summary(include_unknown=True))
    second = ingest_espn_game_summary(db_session, state_id=state.id, summary=_summary(pass_yards=289))

    revisions = db_session.query(PlayerGameStatRevision).order_by(PlayerGameStatRevision.revision_number).all()
    assert first["identity_unmatched"] == 1
    assert second["revisions"] == 1
    assert [revision.stats_json["pass_yards"] for revision in revisions] == [250.0, 289.0]
    assert revisions[-1].supersedes_revision_id == revisions[0].id
    unresolved = db_session.query(UnmatchedProviderRow).one()
    assert unresolved.notes == "IDENTITY_UNMATCHED"
    assert unresolved.mapped_player_id is None
    assert db_session.query(PlayerStat).count() == public_stat_count
    assert db_session.query(ScoringCalculationSnapshot).count() == 0
    assert qb.id == revisions[-1].player_id


def test_polling_circuit_breaker_prevents_aggressive_retries(client, db_session):
    _league, _qb, _game = _espn_identity_ready(db_session)
    ensure_relevant_espn_poll_states(db_session, season=2026, week=1)
    state = db_session.query(ProviderGamePollState).one()
    record_espn_poll_failure(db_session, state_id=state.id, category="RATE_LIMITED", message="too many requests", status_code=429, retry_after=600)
    health = db_session.query(ProviderPollingHealth).one()
    assert state.rate_limited_until and state.rate_limited_until > datetime.now(timezone.utc)
    assert health.circuit_state == "open"
    assert health.blocked_until is not None

    record_espn_poll_failure(db_session, state_id=state.id, category="PROVIDER_BLOCKED", message="blocked", status_code=403)
    assert state.next_poll_at is None
    assert state.operator_status == "provider_blocked"


class _PollingAdapter:
    def __init__(self):
        self.scoreboard_calls = 0
        self.summary_calls = 0

    def fetch_scoreboard(self, *, season, week):
        self.scoreboard_calls += 1
        return (
            EspnGame(
                game_id="espn-game-1", status=IN_PROGRESS, season=season, week=week,
                start_at=datetime.now(timezone.utc), payload={"event": "espn-game-1", "state": "in"},
            ),
        )

    def fetch_game_summary(self, *, game_id, season, week):
        self.summary_calls += 1
        return _summary()


def test_shared_game_poller_fetches_one_boxscore_and_only_shadow_writes(client, db_session, monkeypatch):
    _league, _qb, _game = _espn_identity_ready(db_session)
    public_stat_count = db_session.query(PlayerStat).count()
    monkeypatch.setattr(settings, "espn_live_scoring_enabled", True)
    monkeypatch.setattr(settings, "scoring_mode", "shadow")
    adapter = _PollingAdapter()

    # Bind to this fixture's database; importing a top-level conftest module
    # creates a different in-memory SQLite engine under pytest.
    session_factory = sessionmaker(bind=db_session.get_bind(), autocommit=False, autoflush=False)
    result = run_espn_shadow_poll_iteration(session_factory=session_factory, season=2026, week=1, adapter=adapter)
    # A second 30-second worker tick may not fetch the same active game again:
    # the durable state enforces the three-minute detail-poll interval.
    second = run_espn_shadow_poll_iteration(session_factory=session_factory, season=2026, week=1, adapter=adapter)

    with session_factory() as verify:
        assert result.states_created == 1
        assert result.detail_requests == 1
        assert result.detail_ingested == 1
        assert second.detail_requests == 0
        assert adapter.scoreboard_calls == 1
        assert adapter.summary_calls == 1
        assert verify.query(ProviderRawEvent).filter(ProviderRawEvent.provider == "espn").count() == 2
        assert verify.query(PlayerGameStatRevision).count() == 1
        assert verify.query(PlayerStat).count() == public_stat_count


def test_admin_shadow_status_and_queue_are_private_and_do_not_contact_espn(client, db_session, monkeypatch):
    _league, _qb, _game = _espn_identity_ready(db_session)
    ensure_relevant_espn_poll_states(db_session, season=2026, week=1)
    state = db_session.query(ProviderGamePollState).one()
    state.lifecycle_state = IN_PROGRESS
    db_session.commit()
    monkeypatch.setattr(settings, "espn_live_scoring_enabled", True)
    monkeypatch.setattr(settings, "scoring_mode", "shadow")
    token, _user_id = create_user_and_token(client, "espn-shadow", admin=True)

    status_response = client.get(
        "/admin/scoring/espn-live/status?season=2026&week=1",
        headers=auth_headers(token),
    )
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["mode"] == "shadow_only"
    assert payload["raw_event_count"] == 0
    assert payload["poll_states"][0]["provider_game_id"] == "espn-game-1"
    assert "raw_payload" not in str(payload)

    # The admin action only makes the worker state due. It never performs a
    # provider request inside FastAPI's request/transaction lifecycle.
    queue_response = client.post(
        "/admin/scoring/espn-live/poll/queue?season=2026&week=1",
        headers=auth_headers(token),
    )
    assert queue_response.status_code == 200
    assert queue_response.json() == {"mode": "shadow_only", "season": 2026, "week": 1, "queued": 1}
