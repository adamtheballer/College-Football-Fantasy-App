from __future__ import annotations

import hashlib
import json
import random
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import ESPNClient, extract_player_box_score_stats
from collegefootballfantasy_api.app.models.cfb_ranking_snapshot import CFBRankingSnapshot
from collegefootballfantasy_api.app.models.cfb_standing_snapshot import CFBStandingSnapshot
from collegefootballfantasy_api.app.models.college_football_team import CollegeFootballTeam
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_ingestion_run import ProviderIngestionRun
from collegefootballfantasy_api.app.models.provider_response_cache import ProviderResponseCache
from collegefootballfantasy_api.app.services.espn_stats_sync import _build_player_indexes, _match_player
from collegefootballfantasy_api.app.services.provider_identity_audit import (
    record_provider_identity_audit,
    record_unmatched_provider_row,
)

TARGETS = (
    "teams",
    "schedules",
    "rankings",
    "scores",
    "game_summaries",
    "box_scores",
    "standings",
)
DEFAULT_USER_AGENT = "CollegeFootballFantasy/1.0 ESPN-CFB-ingestion contact=admin"
POWER4_CONFERENCES = ("ACC", "BIG12", "BIG10", "SEC")
DEFAULT_HTTP_CACHE_TTL_MINUTES = 20
MIN_HTTP_CACHE_TTL_MINUTES = 10
MAX_HTTP_CACHE_TTL_MINUTES = 30
DEFAULT_STATS_REFRESH_INTERVAL_SECONDS = 420
STATS_REFRESH_FEEDS = ("scoreboard", "scores", "game_summaries", "box_scores")


class ESPNIngestionError(RuntimeError):
    pass


class ESPNRequestLimitExceeded(ESPNIngestionError):
    pass


class ESPNCacheMiss(ESPNIngestionError):
    pass


class ESPNCircuitBreakerOpen(ESPNIngestionError):
    pass


@dataclass
class CacheStats:
    cache_hits: int = 0
    cache_misses: int = 0
    requests_sent: int = 0
    cache_stale_used: int = 0
    cache_write_errors: int = 0
    circuit_breaker_trips: int = 0
    temp_cache_hits: int = 0
    temp_cache_writes: int = 0


@dataclass(frozen=True)
class ESPNHTTPResult:
    payload: Any
    status_code: int
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False


@dataclass
class PersistStats:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0

    def add(self, other: "PersistStats") -> None:
        self.inserted += other.inserted
        self.updated += other.updated
        self.skipped += other.skipped


@dataclass
class ESPNIngestionSummary:
    provider: str = "espn"
    status: str = "success"
    season: int = 0
    run_date: date | None = None
    targets: list[str] = field(default_factory=list)
    dry_run: bool = False
    cache_hits: int = 0
    cache_misses: int = 0
    requests_sent: int = 0
    cache_stale_used: int = 0
    cache_write_errors: int = 0
    circuit_breaker_trips: int = 0
    temp_cache_hits: int = 0
    temp_cache_writes: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "season": self.season,
            "run_date": self.run_date.isoformat() if self.run_date else None,
            "targets": self.targets,
            "dry_run": self.dry_run,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "requests_sent": self.requests_sent,
            "cache_stale_used": self.cache_stale_used,
            "cache_write_errors": self.cache_write_errors,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "temp_cache_hits": self.temp_cache_hits,
            "temp_cache_writes": self.temp_cache_writes,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _params_hash(method: str, url: str, params: dict[str, Any]) -> str:
    payload = {"method": method.upper(), "url": url, "params": params}
    return hashlib.sha256(_json_key(payload).encode("utf-8")).hexdigest()


def _content_hash(payload: Any) -> str:
    return hashlib.sha256(_json_key(payload).encode("utf-8")).hexdigest()


def _date_key(run_date: date | None) -> str:
    return run_date.isoformat() if run_date else "season"


def _http_cache_ttl_minutes(value: int | None = None) -> int:
    if value is None:
        return DEFAULT_HTTP_CACHE_TTL_MINUTES
    if value < MIN_HTTP_CACHE_TTL_MINUTES or value > MAX_HTTP_CACHE_TTL_MINUTES:
        raise ValueError(
            f"HTTP cache TTL must be between {MIN_HTTP_CACHE_TTL_MINUTES} and "
            f"{MAX_HTTP_CACHE_TTL_MINUTES} minutes"
        )
    return value


def default_cache_ttls(*, http_cache_ttl_minutes: int | None = None) -> dict[str, timedelta]:
    ttl = timedelta(minutes=_http_cache_ttl_minutes(http_cache_ttl_minutes))
    return {feed: ttl for feed in ("teams", "rankings", "standings", "scoreboard", "scores", "schedules", "game_summaries", "box_scores")}


def parse_ttl_overrides(raw: str | None) -> dict[str, timedelta]:
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--cache-ttl-overrides-json must be a JSON object")
    overrides: dict[str, timedelta] = {}
    for feed, seconds in payload.items():
        overrides[str(feed)] = timedelta(seconds=int(seconds))
    return overrides


class TempHTTPResponseCache:
    def __init__(self, cache_dir: str | Path | None = None, *, ttl_seconds: int = DEFAULT_STATS_REFRESH_INTERVAL_SECONDS) -> None:
        self.cache_dir = Path(cache_dir or Path(tempfile.gettempdir()) / "cff_espn_http_cache")
        self.ttl_seconds = ttl_seconds

    def get(self, cache_key: str) -> dict[str, Any] | None:
        path = self._path(cache_key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        expires_at_raw = payload.get("expires_at")
        if not isinstance(expires_at_raw, str):
            return None
        expires_at = datetime.fromisoformat(expires_at_raw)
        if _aware(expires_at) <= _now():
            return None
        return payload

    def set(
        self,
        cache_key: str,
        *,
        payload: Any,
        status_code: int,
        content_type: str | None,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        expires_at = _now() + timedelta(seconds=self.ttl_seconds)
        row = {
            "payload": payload,
            "status_code": status_code,
            "content_type": content_type,
            "etag": etag,
            "last_modified": last_modified,
            "expires_at": expires_at.isoformat(),
        }
        self._path(cache_key).write_text(json.dumps(row, sort_keys=True), encoding="utf-8")

    def _path(self, cache_key: str) -> Path:
        safe_key = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{safe_key}.json"


def live_stats_ttl_overrides(interval_seconds: int = DEFAULT_STATS_REFRESH_INTERVAL_SECONDS) -> dict[str, timedelta]:
    ttl = timedelta(seconds=interval_seconds)
    return {feed: ttl for feed in STATS_REFRESH_FEEDS}


class CachedESPNFetcher:
    def __init__(
        self,
        db: Session,
        *,
        rate_limit_seconds: float = 2.0,
        max_requests_per_run: int = 250,
        cache_only: bool = False,
        force_refresh: bool = False,
        write_cache: bool = True,
        timeout_seconds: float = 20.0,
        max_consecutive_failures: int = 5,
        temp_cache: TempHTTPResponseCache | None = None,
        write_temp_cache: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
        http_get: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self.db = db
        self.rate_limit_seconds = max(0.0, rate_limit_seconds)
        self.max_requests_per_run = max_requests_per_run
        self.cache_only = cache_only
        self.force_refresh = force_refresh
        self.write_cache = write_cache
        self.timeout_seconds = timeout_seconds
        self.max_consecutive_failures = max_consecutive_failures
        self.temp_cache = temp_cache
        self.write_temp_cache = write_temp_cache
        self.user_agent = user_agent
        self.sleeper = sleeper
        self.jitter = jitter
        self.http_get = http_get
        self.stats = CacheStats()
        self._memory_cache: dict[str, Any] = {}
        self._last_request_at: float | None = None
        self._consecutive_failures = 0

    def get_json(
        self,
        *,
        feed: str,
        url: str,
        params: dict[str, Any],
        scope_key: str,
        ttl: timedelta,
    ) -> Any:
        method = "GET"
        params = {key: value for key, value in params.items() if value is not None}
        request_hash = _params_hash(method, url, params)
        memory_key = f"{feed}:{scope_key}:{request_hash}"
        if memory_key in self._memory_cache:
            return self._memory_cache[memory_key]

        if self.temp_cache and not self.force_refresh:
            temp_cached = self.temp_cache.get(memory_key)
            if temp_cached is not None:
                self.stats.temp_cache_hits += 1
                payload = temp_cached.get("payload", {})
                self._memory_cache[memory_key] = payload
                return payload

        cached = self._get_cache(feed=feed, scope_key=scope_key, params_hash=request_hash)
        timestamp = _now()
        if cached and not self.force_refresh and self._is_fresh(cached, timestamp):
            self.stats.cache_hits += 1
            payload = self._cached_payload(cached)
            self._memory_cache[memory_key] = payload
            return payload

        self.stats.cache_misses += 1
        if self.cache_only:
            if cached:
                self.stats.cache_stale_used += 1
                payload = self._cached_payload(cached)
                self._memory_cache[memory_key] = payload
                return payload
            raise ESPNCacheMiss(f"cache-only mode has no cached payload for {feed}:{scope_key}")

        if self.stats.requests_sent >= self.max_requests_per_run:
            raise ESPNRequestLimitExceeded(
                f"ESPN max requests per run exceeded ({self.max_requests_per_run})"
            )
        if self._consecutive_failures >= self.max_consecutive_failures:
            self.stats.circuit_breaker_trips += 1
            if cached:
                self.stats.cache_stale_used += 1
                payload = self._cached_payload(cached)
                self._memory_cache[memory_key] = payload
                return payload
            raise ESPNCircuitBreakerOpen("ESPN circuit breaker is open after repeated failures")

        try:
            result = self._request_json(url, params, cached=cached)
        except Exception:
            self._consecutive_failures += 1
            if cached:
                self.stats.cache_stale_used += 1
                payload = self._cached_payload(cached)
                self._memory_cache[memory_key] = payload
                return payload
            raise
        self._consecutive_failures = 0
        payload = result.payload

        if self.write_cache:
            try:
                self._write_cache(
                    feed=feed,
                    scope_key=scope_key,
                    params_hash=request_hash,
                    method=method,
                    url=url,
                    params=params,
                    payload=payload,
                    status_code=result.status_code,
                    content_type=result.content_type,
                    etag=result.etag or (cached.etag if cached else None),
                    last_modified=result.last_modified or (cached.last_modified if cached else None),
                    expires_at=timestamp + ttl,
                )
            except Exception:
                self.stats.cache_write_errors += 1
                self.db.rollback()

        self._write_temp_cache(memory_key, result)
        self._memory_cache[memory_key] = payload
        return payload

    def _get_cache(self, *, feed: str, scope_key: str, params_hash: str) -> ProviderResponseCache | None:
        stmt = select(ProviderResponseCache).where(
            ProviderResponseCache.provider == "espn",
            ProviderResponseCache.feed == feed,
            ProviderResponseCache.scope_key == scope_key,
            ProviderResponseCache.params_hash == params_hash,
        )
        return self.db.scalar(stmt)

    @staticmethod
    def _is_fresh(row: ProviderResponseCache, now: datetime) -> bool:
        expires_at = _aware(row.expires_at)
        return expires_at is not None and expires_at > now and row.error_message is None

    @staticmethod
    def _cached_payload(row: ProviderResponseCache) -> Any:
        if row.response_json is not None:
            return row.response_json
        if row.response_text:
            return json.loads(row.response_text)
        return {}

    def _request_json(
        self,
        url: str,
        params: dict[str, Any],
        *,
        cached: ProviderResponseCache | None = None,
    ) -> ESPNHTTPResult:
        self._rate_limit()
        self.stats.requests_sent += 1
        headers = {"User-Agent": self.user_agent, "Accept": "application/json,text/plain;q=0.8,*/*;q=0.5"}
        if cached and cached.etag:
            headers["If-None-Match"] = cached.etag
        if cached and cached.last_modified:
            headers["If-Modified-Since"] = cached.last_modified
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                if self.http_get:
                    response = self.http_get(url, params=params, headers=headers, timeout=self.timeout_seconds)
                else:
                    with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                        response = client.get(url, params=params, headers=headers)
                if response.status_code == 304 and cached:
                    return ESPNHTTPResult(
                        payload=self._cached_payload(cached),
                        status_code=304,
                        content_type=cached.content_type,
                        etag=cached.etag,
                        last_modified=cached.last_modified,
                        not_modified=True,
                    )
                if response.status_code == 429 and attempt < 3:
                    self.sleeper(self._retry_delay(attempt, response=response))
                    continue
                if response.status_code >= 500 and attempt < 3:
                    self.sleeper(self._retry_delay(attempt, response=response))
                    continue
                if 400 <= response.status_code < 500:
                    response.raise_for_status()
                response.raise_for_status()
                content_type = response.headers.get("content-type")
                return ESPNHTTPResult(
                    payload=response.json(),
                    status_code=response.status_code,
                    content_type=content_type,
                    etag=response.headers.get("etag"),
                    last_modified=response.headers.get("last-modified"),
                )
            except Exception as exc:
                last_exc = exc
                if isinstance(exc, httpx.HTTPStatusError):
                    status_code = exc.response.status_code
                    if 400 <= status_code < 500 and status_code != 429:
                        raise ESPNIngestionError(f"ESPN non-retryable HTTP {status_code} for {url}") from exc
                if attempt >= 3:
                    break
                self.sleeper(self._retry_delay(attempt))
        raise ESPNIngestionError(f"ESPN request failed for {url}: {last_exc}") from last_exc

    def _retry_delay(self, attempt: int, *, response: httpx.Response | None = None) -> float:
        retry_after = response.headers.get("retry-after") if response else None
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        base = min(30.0, 2 ** (attempt - 1))
        return base + self.jitter(0.0, 0.5)

    def _rate_limit(self) -> None:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            delay = self.rate_limit_seconds - elapsed
            if delay > 0:
                self.sleeper(delay)
        self._last_request_at = time.monotonic()

    def _write_cache(
        self,
        *,
        feed: str,
        scope_key: str,
        params_hash: str,
        method: str,
        url: str,
        params: dict[str, Any],
        payload: Any,
        status_code: int,
        content_type: str | None,
        etag: str | None,
        last_modified: str | None,
        expires_at: datetime,
    ) -> ProviderResponseCache:
        row = self._get_cache(feed=feed, scope_key=scope_key, params_hash=params_hash)
        if not row:
            row = ProviderResponseCache(
                provider="espn",
                feed=feed,
                scope_key=scope_key,
                params_hash=params_hash,
            )
            self.db.add(row)
        row.method = method
        row.url = url
        row.params_json = params
        row.http_status = status_code
        row.content_type = content_type
        row.etag = etag
        row.last_modified = last_modified
        row.response_json = payload
        row.response_text = None
        row.content_hash = _content_hash(payload)
        row.fetched_at = _now()
        row.expires_at = expires_at
        row.error_message = None
        row.meta = {"cache_policy": "ttl_seconds", "ttl_seconds": int((expires_at - row.fetched_at).total_seconds())}
        self.db.flush()
        return row

    def _write_temp_cache(self, memory_key: str, result: ESPNHTTPResult) -> None:
        if not self.temp_cache or not self.write_temp_cache:
            return
        try:
            self.temp_cache.set(
                memory_key,
                payload=result.payload,
                status_code=result.status_code,
                content_type=result.content_type,
                etag=result.etag,
                last_modified=result.last_modified,
            )
            self.stats.temp_cache_writes += 1
        except OSError:
            return


class ESPNCollegeFootballIngestion:
    def __init__(
        self,
        db: Session,
        *,
        fetcher: CachedESPNFetcher,
        http_cache_ttl_minutes: int | None = None,
        ttl_overrides: dict[str, timedelta] | None = None,
    ) -> None:
        self.db = db
        self.fetcher = fetcher
        self.ttls = default_cache_ttls(http_cache_ttl_minutes=http_cache_ttl_minutes)
        self.ttls.update(ttl_overrides or {})

    def run(
        self,
        *,
        season: int,
        run_date: date | None,
        targets: list[str],
        week: int | None = None,
        dry_run: bool = False,
    ) -> ESPNIngestionSummary:
        started_at = _now()
        run_row = ProviderIngestionRun(
            provider="espn",
            status="running",
            season=season,
            run_date=run_date,
            targets=targets,
            dry_run=dry_run,
            started_at=started_at,
        )
        if not dry_run:
            self.db.add(run_row)
            self.db.flush()

        summary = ESPNIngestionSummary(season=season, run_date=run_date, targets=targets, dry_run=dry_run)
        persist_stats = PersistStats()

        try:
            if "teams" in targets:
                persist_stats.add(self.persist_teams(dry_run=dry_run))

            scoreboard = None
            scoreboard_targets = {"schedules", "scores", "game_summaries", "box_scores"}
            if scoreboard_targets.intersection(targets):
                scoreboard = self.fetch_scoreboard(season=season, run_date=run_date, week=week)
                if {"teams", "schedules", "scores"}.intersection(targets):
                    persist_stats.add(
                        self.persist_scoreboard(
                            scoreboard,
                            season=season,
                            default_week=week,
                            dry_run=dry_run,
                            include_teams="teams" not in targets,
                        )
                    )

            if "rankings" in targets:
                persist_stats.add(self.persist_rankings(season=season, week=week or 0, dry_run=dry_run))

            if "standings" in targets:
                persist_stats.add(self.persist_standings(season=season, dry_run=dry_run))

            if "game_summaries" in targets and scoreboard:
                summaries = self.fetch_summaries(scoreboard)
                persist_stats.skipped += len(summaries)

            if "box_scores" in targets and scoreboard:
                persist_stats.add(self.persist_box_scores(scoreboard, season=season, default_week=week, dry_run=dry_run))
        except Exception as exc:
            summary.status = "failed"
            summary.errors.append(str(exc))
            if not dry_run:
                self.db.rollback()
                run_row.status = "failed"
                run_row.error_message = str(exc)
                run_row.completed_at = _now()
                self.db.add(run_row)
                self.db.commit()
            raise

        summary.cache_hits = self.fetcher.stats.cache_hits
        summary.cache_misses = self.fetcher.stats.cache_misses
        summary.requests_sent = self.fetcher.stats.requests_sent
        summary.cache_stale_used = self.fetcher.stats.cache_stale_used
        summary.cache_write_errors = self.fetcher.stats.cache_write_errors
        summary.circuit_breaker_trips = self.fetcher.stats.circuit_breaker_trips
        summary.temp_cache_hits = self.fetcher.stats.temp_cache_hits
        summary.temp_cache_writes = self.fetcher.stats.temp_cache_writes
        summary.inserted = persist_stats.inserted
        summary.updated = persist_stats.updated
        summary.skipped = persist_stats.skipped
        if summary.errors:
            summary.status = "partial"

        if not dry_run:
            run_row.status = summary.status
            run_row.completed_at = _now()
            run_row.cache_hits = summary.cache_hits
            run_row.cache_misses = summary.cache_misses
            run_row.requests_sent = summary.requests_sent
            run_row.cache_stale_used = summary.cache_stale_used
            run_row.cache_write_errors = summary.cache_write_errors
            run_row.inserted = summary.inserted
            run_row.updated = summary.updated
            run_row.skipped = summary.skipped
            run_row.errors = summary.errors
            self.db.commit()
        else:
            self.db.rollback()
        return summary

    def fetch_teams(self) -> dict[str, Any]:
        return self.fetcher.get_json(
            feed="teams",
            url=f"{ESPNClient.SITE_BASE_URL}/teams",
            params={"groups": ESPNClient.FBS_GROUP, "limit": 1000},
            scope_key="fbs",
            ttl=self.ttls["teams"],
        )

    def fetch_scoreboard(self, *, season: int, run_date: date | None, week: int | None) -> dict[str, Any]:
        params: dict[str, Any] = {"groups": ESPNClient.FBS_GROUP, "limit": 1000}
        if week is not None:
            params.update({"dates": season, "seasontype": 2, "week": week})
            scope_key = _json_key({"season": season, "week": week})
        elif run_date is not None:
            params["dates"] = run_date.strftime("%Y%m%d")
            scope_key = _json_key({"date": run_date.isoformat()})
        else:
            params["dates"] = season
            scope_key = _json_key({"season": season})
        return self.fetcher.get_json(
            feed="scoreboard",
            url=f"{ESPNClient.SITE_BASE_URL}/scoreboard",
            params=params,
            scope_key=scope_key,
            ttl=self.ttls["scoreboard"],
        )

    def fetch_rankings(self, *, season: int, week: int) -> dict[str, Any]:
        return self.fetcher.get_json(
            feed="rankings",
            url=f"{ESPNClient.SITE_BASE_URL}/rankings",
            params={"dates": season, "seasontype": 2, "week": week or None},
            scope_key=_json_key({"season": season, "week": week}),
            ttl=self.ttls["rankings"],
        )

    def fetch_standings(self, *, season: int, conference: str) -> dict[str, Any]:
        conference_key = conference.upper().replace(" ", "")
        group = ESPNClient.CONFERENCE_GROUPS[conference_key]
        return self.fetcher.get_json(
            feed="standings",
            url=f"{ESPNClient.BASE_URL}/standings",
            params={"group": group, "season": season},
            scope_key=_json_key({"season": season, "conference": conference_key}),
            ttl=self.ttls["standings"],
        )

    def fetch_summaries(self, scoreboard: dict[str, Any]) -> list[dict[str, Any]]:
        summaries = []
        for event in _scoreboard_events(scoreboard):
            event_id = event.get("id")
            if not event_id:
                continue
            payload = self.fetcher.get_json(
                feed="game_summaries",
                url=f"{ESPNClient.SITE_BASE_URL}/summary",
                params={"event": event_id},
                scope_key=_json_key({"event": event_id}),
                ttl=self.ttls["game_summaries"],
            )
            if isinstance(payload, dict):
                payload.setdefault("event_id", str(event_id))
                summaries.append(payload)
        return summaries

    def persist_scoreboard(
        self,
        scoreboard: dict[str, Any],
        *,
        season: int,
        default_week: int | None,
        dry_run: bool,
        include_teams: bool = True,
    ) -> PersistStats:
        stats = PersistStats()
        for event in _scoreboard_events(scoreboard):
            game_row = normalize_scoreboard_game(event, season=season, default_week=default_week)
            if not game_row:
                stats.skipped += 1
                continue
            teams = game_row.pop("teams")
            if include_teams:
                for team_payload in teams:
                    stats.add(self.upsert_team(team_payload, dry_run=dry_run))
            stats.add(self.upsert_game(game_row, dry_run=dry_run))
        return stats

    def persist_teams(self, *, dry_run: bool) -> PersistStats:
        payload = self.fetch_teams()
        stats = PersistStats()
        for row in normalize_teams(payload):
            stats.add(self.upsert_team(row, dry_run=dry_run))
        return stats

    def persist_rankings(self, *, season: int, week: int, dry_run: bool) -> PersistStats:
        payload = self.fetch_rankings(season=season, week=week)
        rows = normalize_rankings(payload, season=season, week=week)
        stats = PersistStats()
        for row in rows:
            existing = self.db.scalar(
                select(CFBRankingSnapshot).where(
                    CFBRankingSnapshot.provider == "espn",
                    CFBRankingSnapshot.poll == row["poll"],
                    CFBRankingSnapshot.season == season,
                    CFBRankingSnapshot.week == week,
                    CFBRankingSnapshot.team_external_id == row["team_external_id"],
                )
            )
            if dry_run:
                stats.updated += 1 if existing else 0
                stats.inserted += 0 if existing else 1
                continue
            if existing:
                for key, value in row.items():
                    setattr(existing, key, value)
                stats.updated += 1
            else:
                self.db.add(CFBRankingSnapshot(**row))
                stats.inserted += 1
        return stats

    def persist_standings(self, *, season: int, dry_run: bool) -> PersistStats:
        stats = PersistStats()
        for conference in POWER4_CONFERENCES:
            payload = self.fetch_standings(season=season, conference=conference)
            for row in normalize_standings(payload, season=season, conference=conference):
                existing = self.db.scalar(
                    select(CFBStandingSnapshot).where(
                        CFBStandingSnapshot.team_name == row["team_name"],
                        CFBStandingSnapshot.conference == row["conference"],
                        CFBStandingSnapshot.season == row["season"],
                    )
                )
                if dry_run:
                    stats.updated += 1 if existing else 0
                    stats.inserted += 0 if existing else 1
                    continue
                if existing:
                    for key, value in row.items():
                        setattr(existing, key, value)
                    stats.updated += 1
                else:
                    self.db.add(CFBStandingSnapshot(**row))
                    stats.inserted += 1
        return stats

    def persist_box_scores(
        self,
        scoreboard: dict[str, Any],
        *,
        season: int,
        default_week: int | None,
        dry_run: bool,
    ) -> PersistStats:
        stats = PersistStats()
        players = self.db.query(Player).all()
        external_index, name_school_index = _build_player_indexes(players)
        games_by_external_id = {
            str(game.external_id): game
            for game in self.db.query(Game).filter(Game.external_id.isnot(None)).all()
        }

        for summary in self.fetch_summaries(scoreboard):
            event_id = str(summary.get("event_id") or summary.get("header", {}).get("id") or "")
            game = games_by_external_id.get(event_id)
            event_week = default_week or _summary_week(summary) or 0
            rows = extract_player_box_score_stats(summary)
            for row in rows:
                player, match_type, reason = _match_player(row, external_index, name_school_index)
                if not player:
                    if not dry_run:
                        record_unmatched_provider_row(
                            self.db,
                            provider="espn",
                            season=season,
                            week=event_week,
                            row=row,
                            reason=reason,
                        )
                    stats.skipped += 1
                    continue
                if not dry_run:
                    record_provider_identity_audit(
                        self.db,
                        provider="espn",
                        season=season,
                        week=event_week,
                        row=row,
                        player_id=player.id,
                        match_type=match_type,
                        confidence=100 if match_type == "external_id" else 70,
                    )
                stats.add(self.upsert_player_stat(player.id, season, event_week, row, dry_run=dry_run))
                if game:
                    stats.add(self.upsert_player_game_stat(player.id, game.id, season, event_week, row, dry_run=dry_run))
        return stats

    def upsert_team(self, row: dict[str, Any], *, dry_run: bool) -> PersistStats:
        external_id = str(row.get("external_id") or "")
        if not external_id:
            return PersistStats(skipped=1)
        existing = self.db.scalar(
            select(CollegeFootballTeam).where(
                CollegeFootballTeam.provider == "espn",
                CollegeFootballTeam.external_id == external_id,
            )
        )
        if dry_run:
            return PersistStats(updated=1 if existing else 0, inserted=0 if existing else 1)
        if existing:
            for key, value in row.items():
                setattr(existing, key, value)
            return PersistStats(updated=1)
        self.db.add(CollegeFootballTeam(provider="espn", **row))
        return PersistStats(inserted=1)

    def upsert_game(self, row: dict[str, Any], *, dry_run: bool) -> PersistStats:
        existing = self.db.scalar(select(Game).where(Game.external_id == row["external_id"]))
        if dry_run:
            return PersistStats(updated=1 if existing else 0, inserted=0 if existing else 1)
        if existing:
            for key, value in row.items():
                setattr(existing, key, value)
            return PersistStats(updated=1)
        self.db.add(Game(**row))
        return PersistStats(inserted=1)

    def upsert_player_stat(
        self,
        player_id: int,
        season: int,
        week: int,
        row: dict[str, Any],
        *,
        dry_run: bool,
    ) -> PersistStats:
        existing = self.db.scalar(
            select(PlayerStat).where(
                PlayerStat.player_id == player_id,
                PlayerStat.season == season,
                PlayerStat.week == week,
            )
        )
        if dry_run:
            return PersistStats(updated=1 if existing else 0, inserted=0 if existing else 1)
        if existing:
            existing.source = "espn"
            existing.stats = row
            return PersistStats(updated=1)
        self.db.add(PlayerStat(player_id=player_id, season=season, week=week, source="espn", stats=row))
        return PersistStats(inserted=1)

    def upsert_player_game_stat(
        self,
        player_id: int,
        game_id: int,
        season: int,
        week: int,
        row: dict[str, Any],
        *,
        dry_run: bool,
    ) -> PersistStats:
        existing = self.db.scalar(
            select(PlayerGameStat).where(
                PlayerGameStat.player_id == player_id,
                PlayerGameStat.game_id == game_id,
            )
        )
        if dry_run:
            return PersistStats(updated=1 if existing else 0, inserted=0 if existing else 1)
        if existing:
            existing.source = "espn"
            existing.stats = row
            return PersistStats(updated=1)
        self.db.add(
            PlayerGameStat(
                player_id=player_id,
                game_id=game_id,
                season=season,
                week=week,
                source="espn",
                stats=row,
            )
        )
        return PersistStats(inserted=1)


def _scoreboard_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events = payload.get("events")
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, dict)]


def _team_row(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_id": str(team.get("id") or ""),
        "name": str(team.get("name") or team.get("displayName") or team.get("shortDisplayName") or "").strip(),
        "display_name": team.get("displayName"),
        "short_name": team.get("shortDisplayName"),
        "abbreviation": team.get("abbreviation"),
        "location": team.get("location"),
        "conference": (team.get("conference") or {}).get("name") if isinstance(team.get("conference"), dict) else None,
        "color": team.get("color"),
        "alternate_color": team.get("alternateColor"),
        "logos": team.get("logos") if isinstance(team.get("logos"), list) else [],
        "raw_json": team,
    }


def normalize_teams(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    team_entries = payload.get("teams")
    if not isinstance(team_entries, list):
        team_entries = []
        sports = payload.get("sports")
        if isinstance(sports, list):
            for sport in sports:
                if not isinstance(sport, dict):
                    continue
                leagues = sport.get("leagues")
                if not isinstance(leagues, list):
                    continue
                for league in leagues:
                    if isinstance(league, dict) and isinstance(league.get("teams"), list):
                        team_entries.extend(league["teams"])
    for entry in team_entries:
        if not isinstance(entry, dict):
            continue
        team = entry.get("team") if isinstance(entry.get("team"), dict) else entry
        row = _team_row(team)
        if row["external_id"] and row["name"]:
            rows.append(row)
    return rows


def normalize_scoreboard_game(event: dict[str, Any], *, season: int, default_week: int | None) -> dict[str, Any] | None:
    event_id = str(event.get("id") or "")
    competitions = event.get("competitions")
    if not event_id or not isinstance(competitions, list) or not competitions:
        return None
    competition = competitions[0]
    if not isinstance(competition, dict):
        return None
    competitors = competition.get("competitors")
    if not isinstance(competitors, list):
        return None

    home = None
    away = None
    teams = []
    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        team = competitor.get("team")
        if not isinstance(team, dict):
            continue
        teams.append(_team_row(team))
        if competitor.get("homeAway") == "home":
            home = competitor
        elif competitor.get("homeAway") == "away":
            away = competitor
    if not home or not away:
        return None

    week = default_week or int((event.get("week") or {}).get("number") or 0)
    start_date = _parse_datetime(competition.get("date") or event.get("date"))
    return {
        "external_id": event_id,
        "season": season,
        "week": week,
        "season_type": "regular",
        "start_date": start_date,
        "home_team": _team_name(home),
        "away_team": _team_name(away),
        "home_points": _score(home),
        "away_points": _score(away),
        "neutral_site": bool(competition.get("neutralSite") or False),
        "teams": teams,
    }


def _team_name(competitor: dict[str, Any]) -> str:
    team = competitor.get("team")
    if not isinstance(team, dict):
        return ""
    return str(team.get("location") or team.get("displayName") or team.get("name") or "").strip()


def _score(competitor: dict[str, Any]) -> int | None:
    value = competitor.get("score")
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _summary_week(summary: dict[str, Any]) -> int | None:
    header = summary.get("header")
    if not isinstance(header, dict):
        return None
    week = header.get("week")
    if not isinstance(week, dict):
        return None
    try:
        return int(week.get("number"))
    except (TypeError, ValueError):
        return None


def normalize_rankings(payload: dict[str, Any], *, season: int, week: int) -> list[dict[str, Any]]:
    polls = payload.get("rankings") or payload.get("polls") or []
    if isinstance(polls, dict):
        polls = [polls]
    rows: list[dict[str, Any]] = []
    for poll in polls if isinstance(polls, list) else []:
        if not isinstance(poll, dict):
            continue
        poll_name = str(poll.get("name") or poll.get("shortName") or "ranking")
        ranks = poll.get("ranks") or poll.get("teams") or []
        for entry in ranks if isinstance(ranks, list) else []:
            if not isinstance(entry, dict):
                continue
            team = entry.get("team") if isinstance(entry.get("team"), dict) else entry
            team_external_id = str(team.get("id") or entry.get("teamId") or "")
            team_name = str(team.get("displayName") or team.get("location") or entry.get("team") or "")
            rank = _int(entry.get("current") or entry.get("rank") or entry.get("ranking"))
            if not team_external_id or not team_name or rank is None:
                continue
            rows.append(
                {
                    "provider": "espn",
                    "poll": poll_name,
                    "season": season,
                    "week": week,
                    "team_external_id": team_external_id,
                    "team_name": team_name,
                    "rank": rank,
                    "previous_rank": _int(entry.get("previous")),
                    "points": _int(entry.get("points")),
                    "first_place_votes": _int(entry.get("firstPlaceVotes")),
                    "record_summary": entry.get("recordSummary") or entry.get("record"),
                    "raw_json": entry,
                }
            )
    return rows


def normalize_standings(payload: dict[str, Any], *, season: int, conference: str) -> list[dict[str, Any]]:
    standings = payload.get("standings")
    entries = standings.get("entries") if isinstance(standings, dict) else payload.get("entries")
    if not isinstance(entries, list):
        return []
    rows: list[dict[str, Any]] = []
    for idx, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        team = entry.get("team") if isinstance(entry.get("team"), dict) else {}
        stats = entry.get("stats") if isinstance(entry.get("stats"), list) else []
        team_name = str(
            team.get("location")
            or team.get("displayName")
            or team.get("shortDisplayName")
            or entry.get("team")
            or ""
        ).strip()
        if not team_name:
            continue
        summary_by_name = {str(stat.get("name")): stat.get("summary") for stat in stats if isinstance(stat, dict)}
        overall = _record(summary_by_name.get("overall") or summary_by_name.get("total"))
        conf = _record(summary_by_name.get("conference") or summary_by_name.get("vsconf"))
        rows.append(
            {
                "team_name": team_name,
                "conference": conference,
                "season": season,
                "conference_rank": idx,
                "conference_wins": conf[0],
                "conference_losses": conf[1],
                "overall_wins": overall[0],
                "overall_losses": overall[1],
                "source": "espn",
            }
        )
    return rows


def _record(summary: Any) -> tuple[int | None, int | None]:
    if not isinstance(summary, str) or "-" not in summary:
        return None, None
    left, right = summary.split("-", 1)
    try:
        return int(left), int(right)
    except ValueError:
        return None, None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except ValueError:
        return None


def validate_targets(targets: list[str]) -> list[str]:
    invalid = sorted(set(targets) - set(TARGETS))
    if invalid:
        raise ValueError(f"unsupported ESPN ingestion targets: {', '.join(invalid)}")
    return list(dict.fromkeys(targets))
