from datetime import datetime, timedelta, timezone

import httpx
import pytest

from collegefootballfantasy_api.app.models.college_football_team import CollegeFootballTeam
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.provider_ingestion_run import ProviderIngestionRun
from collegefootballfantasy_api.app.models.provider_response_cache import ProviderResponseCache
from collegefootballfantasy_api.app.services.espn_ingestion_service import (
    CachedESPNFetcher,
    ESPNCircuitBreakerOpen,
    ESPNCacheMiss,
    ESPNCollegeFootballIngestion,
    ESPNRequestLimitExceeded,
    TempHTTPResponseCache,
    _content_hash,
    _json_key,
    _params_hash,
)


def _response(url: str, status_code: int, payload: dict, headers: dict[str, str] | None = None) -> httpx.Response:
    response_headers = {"content-type": "application/json"}
    response_headers.update(headers or {})
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", url),
        headers=response_headers,
    )


def _cached_row(*, feed: str, url: str, params: dict, payload: dict, expires_delta: timedelta) -> ProviderResponseCache:
    now = datetime.now(timezone.utc)
    return ProviderResponseCache(
        provider="espn",
        feed=feed,
        scope_key="scope",
        params_hash=_params_hash("GET", url, params),
        method="GET",
        url=url,
        params_json=params,
        http_status=200,
        content_type="application/json",
        etag='"abc123"',
        last_modified="Wed, 01 Jul 2026 12:00:00 GMT",
        response_json=payload,
        content_hash=_content_hash(payload),
        fetched_at=now,
        expires_at=now + expires_delta,
        meta={},
    )


def _scoreboard_payload() -> dict:
    return {
        "events": [
            {
                "id": "401",
                "date": "2026-09-05T20:00:00Z",
                "week": {"number": 1},
                "competitions": [
                    {
                        "date": "2026-09-05T20:00:00Z",
                        "neutralSite": False,
                        "competitors": [
                            {
                                "homeAway": "home",
                                "score": "31",
                                "team": {
                                    "id": "251",
                                    "location": "Texas",
                                    "name": "Longhorns",
                                    "displayName": "Texas Longhorns",
                                    "shortDisplayName": "Texas",
                                    "abbreviation": "TEX",
                                },
                            },
                            {
                                "homeAway": "away",
                                "score": "24",
                                "team": {
                                    "id": "333",
                                    "location": "Alabama",
                                    "name": "Crimson Tide",
                                    "displayName": "Alabama Crimson Tide",
                                    "shortDisplayName": "Alabama",
                                    "abbreviation": "ALA",
                                },
                            },
                        ],
                    }
                ],
            }
        ]
    }


def test_cache_hit_returns_cached_payload_without_http(client, db_session):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
    params = {"dates": "20260905"}
    db_session.add(
        _cached_row(
            feed="scoreboard",
            url=url,
            params=params,
            payload={"events": []},
            expires_delta=timedelta(hours=1),
        )
    )
    db_session.commit()

    def fail_http(*args, **kwargs):
        raise AssertionError("HTTP should not be called on cache hit")

    fetcher = CachedESPNFetcher(db_session, http_get=fail_http, sleeper=lambda _: None)

    payload = fetcher.get_json(
        feed="scoreboard",
        url=url,
        params=params,
        scope_key="scope",
        ttl=timedelta(minutes=5),
    )

    assert payload == {"events": []}
    assert fetcher.stats.cache_hits == 1
    assert fetcher.stats.requests_sent == 0


def test_expired_cache_sends_one_request_and_refreshes_cache(client, db_session):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
    params = {"dates": "20260905"}
    db_session.add(
        _cached_row(
            feed="scoreboard",
            url=url,
            params=params,
            payload={"events": []},
            expires_delta=timedelta(minutes=-1),
        )
    )
    db_session.commit()
    calls = []

    def http_get(url_arg, **kwargs):
        calls.append(url_arg)
        return _response(url_arg, 200, {"events": [{"id": "401"}]})

    fetcher = CachedESPNFetcher(db_session, http_get=http_get, sleeper=lambda _: None)

    payload = fetcher.get_json(
        feed="scoreboard",
        url=url,
        params=params,
        scope_key="scope",
        ttl=timedelta(minutes=5),
    )

    assert payload == {"events": [{"id": "401"}]}
    assert calls == [url]
    cached = db_session.query(ProviderResponseCache).one()
    assert cached.response_json == {"events": [{"id": "401"}]}
    assert fetcher.stats.cache_misses == 1
    assert fetcher.stats.requests_sent == 1


def test_stale_cache_sends_conditional_headers_and_304_extends_cache(client, db_session):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
    params = {"dates": "20260905"}
    original = {"events": [{"id": "cached"}]}
    db_session.add(
        _cached_row(
            feed="scoreboard",
            url=url,
            params=params,
            payload=original,
            expires_delta=timedelta(minutes=-1),
        )
    )
    db_session.commit()
    seen_headers = {}

    def http_get(url_arg, **kwargs):
        seen_headers.update(kwargs["headers"])
        return httpx.Response(304, request=httpx.Request("GET", url_arg))

    fetcher = CachedESPNFetcher(db_session, http_get=http_get, sleeper=lambda _: None)

    payload = fetcher.get_json(
        feed="scoreboard",
        url=url,
        params=params,
        scope_key="scope",
        ttl=timedelta(minutes=20),
    )

    assert payload == original
    assert seen_headers["If-None-Match"] == '"abc123"'
    assert seen_headers["If-Modified-Since"] == "Wed, 01 Jul 2026 12:00:00 GMT"
    cached = db_session.query(ProviderResponseCache).one()
    assert cached.http_status == 304
    assert cached.response_json == original
    assert cached.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)


def test_failed_espn_response_preserves_and_uses_stale_cache(client, db_session):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
    params = {"dates": "20260905"}
    original = {"events": [{"id": "old"}]}
    db_session.add(
        _cached_row(
            feed="scoreboard",
            url=url,
            params=params,
            payload=original,
            expires_delta=timedelta(minutes=-1),
        )
    )
    db_session.commit()

    def http_get(url_arg, **kwargs):
        return _response(url_arg, 500, {"error": "provider down"})

    fetcher = CachedESPNFetcher(db_session, http_get=http_get, sleeper=lambda _: None)

    payload = fetcher.get_json(
        feed="scoreboard",
        url=url,
        params=params,
        scope_key="scope",
        ttl=timedelta(minutes=5),
    )

    assert payload == original
    assert db_session.query(ProviderResponseCache).one().response_json == original
    assert fetcher.stats.cache_stale_used == 1


def test_4xx_response_is_not_retried_without_stale_cache(client, db_session):
    calls = []

    def http_get(url_arg, **kwargs):
        calls.append(url_arg)
        return _response(url_arg, 403, {"error": "blocked"})

    fetcher = CachedESPNFetcher(db_session, http_get=http_get, sleeper=lambda _: None)

    with pytest.raises(Exception):
        fetcher.get_json(
            feed="scoreboard",
            url="https://example.test/scoreboard",
            params={},
            scope_key="scope",
            ttl=timedelta(minutes=20),
        )

    assert len(calls) == 1


def test_429_uses_retry_after_before_retrying(client, db_session):
    calls = []
    sleeps = []

    def http_get(url_arg, **kwargs):
        calls.append(url_arg)
        if len(calls) == 1:
            return _response(url_arg, 429, {"error": "slow down"}, headers={"retry-after": "3"})
        return _response(url_arg, 200, {"ok": True})

    fetcher = CachedESPNFetcher(db_session, http_get=http_get, sleeper=sleeps.append, jitter=lambda _a, _b: 0)

    payload = fetcher.get_json(
        feed="scoreboard",
        url="https://example.test/scoreboard",
        params={},
        scope_key="scope",
        ttl=timedelta(minutes=20),
    )

    assert payload == {"ok": True}
    assert len(calls) == 2
    assert sleeps == [3.0]


def test_circuit_breaker_stops_after_repeated_provider_failures(client, db_session):
    def http_get(url_arg, **kwargs):
        return _response(url_arg, 500, {"error": "down"})

    fetcher = CachedESPNFetcher(
        db_session,
        http_get=http_get,
        sleeper=lambda _: None,
        jitter=lambda _a, _b: 0,
        max_consecutive_failures=1,
    )

    with pytest.raises(Exception):
        fetcher.get_json(
            feed="one",
            url="https://example.test/one",
            params={},
            scope_key="scope",
            ttl=timedelta(minutes=20),
        )

    with pytest.raises(ESPNCircuitBreakerOpen):
        fetcher.get_json(
            feed="two",
            url="https://example.test/two",
            params={},
            scope_key="scope",
            ttl=timedelta(minutes=20),
        )

    assert fetcher.stats.circuit_breaker_trips == 1


def test_cache_only_fails_when_required_payload_is_missing(client, db_session):
    fetcher = CachedESPNFetcher(db_session, cache_only=True, sleeper=lambda _: None)

    with pytest.raises(ESPNCacheMiss):
        fetcher.get_json(
            feed="scoreboard",
            url="https://example.test/scoreboard",
            params={},
            scope_key="scope",
            ttl=timedelta(minutes=5),
        )


def test_max_requests_per_run_stops_unsafe_runs(client, db_session):
    def http_get(url_arg, **kwargs):
        return _response(url_arg, 200, {"ok": True})

    fetcher = CachedESPNFetcher(
        db_session,
        http_get=http_get,
        sleeper=lambda _: None,
        max_requests_per_run=1,
    )

    fetcher.get_json(
        feed="one",
        url="https://example.test/one",
        params={},
        scope_key="scope",
        ttl=timedelta(minutes=5),
    )

    with pytest.raises(ESPNRequestLimitExceeded):
        fetcher.get_json(
            feed="two",
            url="https://example.test/two",
            params={},
            scope_key="scope",
            ttl=timedelta(minutes=5),
        )


def test_same_url_is_deduped_inside_one_run(client, db_session):
    calls = []

    def http_get(url_arg, **kwargs):
        calls.append(url_arg)
        return _response(url_arg, 200, {"ok": True})

    fetcher = CachedESPNFetcher(db_session, http_get=http_get, sleeper=lambda _: None)
    kwargs = {
        "feed": "scoreboard",
        "url": "https://example.test/scoreboard",
        "params": {"dates": "20260905"},
        "scope_key": "scope",
        "ttl": timedelta(minutes=5),
    }

    assert fetcher.get_json(**kwargs) == {"ok": True}
    assert fetcher.get_json(**kwargs) == {"ok": True}
    assert calls == ["https://example.test/scoreboard"]
    assert fetcher.stats.requests_sent == 1


def test_temp_http_cache_reuses_payload_across_fetchers(client, db_session, tmp_path):
    calls = []
    temp_cache = TempHTTPResponseCache(tmp_path, ttl_seconds=420)

    def http_get(url_arg, **kwargs):
        calls.append(url_arg)
        return _response(url_arg, 200, {"events": [{"id": "cached-temp"}]})

    first = CachedESPNFetcher(
        db_session,
        http_get=http_get,
        sleeper=lambda _: None,
        temp_cache=temp_cache,
        write_cache=False,
    )
    kwargs = {
        "feed": "scoreboard",
        "url": "https://example.test/scoreboard",
        "params": {"dates": "20260905"},
        "scope_key": "scope",
        "ttl": timedelta(minutes=20),
    }

    assert first.get_json(**kwargs) == {"events": [{"id": "cached-temp"}]}
    assert first.stats.temp_cache_writes == 1

    second = CachedESPNFetcher(
        db_session,
        http_get=http_get,
        sleeper=lambda _: None,
        temp_cache=temp_cache,
        write_cache=False,
    )

    assert second.get_json(**kwargs) == {"events": [{"id": "cached-temp"}]}
    assert second.stats.temp_cache_hits == 1
    assert calls == ["https://example.test/scoreboard"]


def test_dry_run_reads_cache_but_does_not_write_normalized_records(client, db_session):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
    params = {"dates": "20260905", "groups": 80, "limit": 1000}
    cache_row = _cached_row(
        feed="scoreboard",
        url=url,
        params=params,
        payload=_scoreboard_payload(),
        expires_delta=timedelta(hours=1),
    )
    cache_row.scope_key = _json_key({"date": "2026-09-05"})
    db_session.add(cache_row)
    db_session.commit()

    fetcher = CachedESPNFetcher(db_session, cache_only=True, write_cache=False, sleeper=lambda _: None)
    service = ESPNCollegeFootballIngestion(db_session, fetcher=fetcher)

    summary = service.run(
        season=2026,
        run_date=datetime(2026, 9, 5).date(),
        targets=["schedules", "scores"],
        dry_run=True,
    )

    assert summary.cache_hits == 1
    assert summary.inserted == 3
    assert db_session.query(CollegeFootballTeam).count() == 0
    assert db_session.query(Game).count() == 0
    assert db_session.query(ProviderIngestionRun).count() == 0
