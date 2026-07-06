# ESPN College Football Ingestion

This job ingests ESPN college football data through cache-first HTTP requests and stores normalized records in the app database.

## Compliance and Safety

- The job uses public ESPN JSON endpoints when available.
- It does not bypass authentication, paywalls, CAPTCHAs, bot protections, or rate limits.
- ESPN `www.espn.com/robots.txt` disallows paths including `*/boxscore?`, so the job avoids scraping those HTML boxscore pages and uses JSON summary endpoints instead.
- The scheduled workflow never uses `--force-refresh`.
- Default request pacing is 2 seconds between ESPN requests.
- ESPN requests are serial only; `--max-concurrent-requests` must be `1`.
- The default HTTP cache TTL is 20 minutes and must stay within 10-30 minutes.
- Failed ESPN responses do not overwrite a valid cached response.
- Stale cached responses are reused if ESPN fails.

ESPN should be treated as an internal-alpha/fallback source unless legal/product review approves it for production use.

## Manual Run

```bash
PYTHONPATH=. uv run python scripts/ingest_espn_college_football.py \
  --season 2026 \
  --date 2026-09-05 \
  --targets teams,schedules,rankings,scores,game_summaries,box_scores,standings
```

Dry run:

```bash
PYTHONPATH=. uv run python scripts/ingest_espn_college_football.py \
  --season 2026 \
  --date 2026-09-05 \
  --targets teams,schedules,scores \
  --dry-run
```

Cache-only emergency/test mode:

```bash
PYTHONPATH=. uv run python scripts/ingest_espn_college_football.py \
  --season 2026 \
  --date 2026-09-05 \
  --targets scores,box_scores \
  --cache-only
```

Live/stat refresh loop with a 7-minute timer:

```bash
PYTHONPATH=. uv run python scripts/ingest_espn_college_football.py \
  --season 2026 \
  --date 2026-09-05 \
  --targets scores,game_summaries,box_scores \
  --watch \
  --refresh-interval-seconds 420
```

This wakes up every 7 minutes, uses a temp HTTP cache between loop cycles, and applies a 420-second TTL override for `scoreboard`, `scores`, `game_summaries`, and `box_scores`.

## Configuration

| Variable / Flag | Required | Default | Description |
|---|---:|---|---|
| `DATABASE_URL` / `--storage-url` | Yes | app default | SQLAlchemy database URL. |
| `--season` | No | current year | Season to ingest. |
| `--date` | No | today | Date to ingest, `YYYY-MM-DD`. |
| `--week` | No | inferred/none | ESPN week override for season/week scoreboard calls. |
| `--targets` | No | all targets | Comma-separated targets. |
| `--dry-run` | No | false | Parse and count without writing normalized records. |
| `--watch` | No | false | Keep refreshing on a timer for live/stat windows. |
| `--refresh-interval-seconds` | No | 420 | Watch-mode refresh timer and temp cache TTL. |
| `--cache-only` | No | false | Use cache only; fail if required payload is missing. |
| `--force-refresh` | No | false | Dangerous manual override that bypasses fresh cache. |
| `--temp-http-cache-dir` | No | system temp | Directory for short-lived temp JSON response cache. |
| `--disable-temp-http-cache` | No | false | Disable temp response cache. |
| `--rate-limit-seconds` | No | 2 | Delay between ESPN requests. |
| `--http-cache-ttl-minutes` | No | 20 | HTTP response cache TTL. Must be 10-30. |
| `--max-requests-per-run` | No | 250 | Safety cap for ESPN requests in one run. |
| `--max-concurrent-requests` | No | 1 | Must remain 1; ESPN ingestion is intentionally serial. |
| `--cache-ttl-overrides-json` | No | none | JSON object of feed TTL seconds. |
| `--output-location` | No | `data/espn_college_football` | Writes `latest_summary.json`. |

## Daily Schedule

The GitHub Actions workflow is `.github/workflows/espn-cfb-ingestion.yml`.

It schedules:

```yaml
cron: "0 13,14 * * *"
```

The workflow gates execution to 6:00 AM `America/Los_Angeles`, which handles PST/PDT without running the ingestion twice.

Required GitHub secret:

```text
ESPN_INGESTION_DATABASE_URL
```

If that is not set, the workflow falls back to `STAGING_DATABASE_URL`.

## Storage

Normalized records are written to:

- `college_football_teams`
- `games`
- `cfb_ranking_snapshots`
- `cfb_standing_snapshots`
- `player_stats`
- `player_game_stats`
- `provider_unmatched_player_rows`
- `provider_player_identity_audits`
- `provider_ingestion_runs`

Response cache records are written to:

- `provider_response_cache`

Cache keys use:

```text
provider + feed + scope_key + params_hash
```

## Cache Behavior

- HTTP responses are cached in `provider_response_cache`.
- Short-lived temp JSON responses are also cached under the system temp directory by default.
- Cache keys are `provider + feed + scope_key + params_hash`.
- `params_hash` is based on method, URL, and sorted query parameters.
- Default HTTP cache TTL is 20 minutes.
- Watch mode uses `--refresh-interval-seconds 420` as the temp cache TTL and applies a 420-second TTL override to live stat feeds.
- TTL can be set with `--http-cache-ttl-minutes`, constrained to 10-30 minutes.
- Per-feed TTL overrides are available through `--cache-ttl-overrides-json`.
- Cached `ETag` and `Last-Modified` values are sent as `If-None-Match` and `If-Modified-Since` when refreshing stale cache rows.
- ESPN `304 Not Modified` responses extend the cache without reparsing a new response body.
- Normalized data uses DB upserts/unique keys, so repeated runs update existing records instead of creating duplicates.

## ESPN Request Safety Controls

- Concurrency is fixed at 1 request at a time.
- Default delay between ESPN requests is 2 seconds.
- Default request budget is 250 requests per run.
- 4xx responses other than 429 are not retried.
- 429 responses respect `Retry-After` when present.
- 5xx responses retry with exponential backoff plus jitter.
- A circuit breaker opens after repeated provider failures.
- Existing stale cache is used when ESPN is failing and a previous valid response exists.
- `--force-refresh` bypasses fresh cache and should only be used manually for debugging.

## Tests

```bash
PYTHONPATH=. uv run pytest -q tests/api/test_espn_ingestion_cache.py
PYTHONPATH=. uv run pytest -q tests
```

The ingestion tests use mocked HTTP responses and local payloads. They do not call live ESPN.

## Troubleshooting

- If `--cache-only` fails, run once without `--cache-only` during an allowed ingestion window.
- If `requests_sent` approaches `--max-requests-per-run`, reduce targets or increase cache TTLs.
- If ESPN returns 403/429 or markup/API shape changes, stop and use an official provider rather than bypassing controls.
