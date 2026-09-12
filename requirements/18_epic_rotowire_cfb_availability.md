# Epic: Reliable RotoWire CFB Availability

## Summary

Replace the legacy HTML-scraped RotoWire injury import with a server-side,
auditable RotoWire CFB availability pipeline. The pipeline must preserve a
negative availability designation until newer affirmative evidence, a verified
game participation event, or an active admin override changes it. A missing
provider item, blank status, empty response, or provider failure must never be
interpreted as healthy.

## Architecture Audit

### Current player identity

- `players.external_id` stores a legacy external identifier.
- `player_provider_ids` persists provider-specific player IDs with uniqueness
  constraints by provider/player and player/provider, an audit trail, and an
  unmatched-provider queue.
- Existing provider mappings are the correct foundation for RotoWire IDs. A
  `sportsdata` provider mapping is preferred for an exact `SportDataIOId`
  crosswalk; fuzzy name matching is not an acceptable fallback for ambiguity.

### Current availability and news state

- `injuries` is a weekly snapshot used by card and roster read paths.
- `player_availability_events` stores sourced, bounded availability assertions
  and is already consumed by projection-context workflows.
- `player_news_events` stores reviewed player-news metadata for the player
  card news tab.
- `provider_sync_states` records last attempt/success/failure for provider
  feeds, but does not retain individual raw provider events or a complete sync
  run audit.

### Current ingestion and failure mode

- `api/app/integrations/rotowire.py` is a legacy public-web-page HTML scraper.
- `scripts/ingest_injuries.py` maps an unknown or blank source status to
  `FULL`; it also creates a player from a name/team match. Both are unsafe for
  production availability decisions.
- Player cards query only the current fantasy-week `injuries` snapshot. A
  designation can therefore disappear when the week changes or when a source
  has no row for the player.
- Official SEC, Big Ten, Big 12, and ACC report ingestion already creates
  source-linked availability/news events twice daily. It is authoritative for
  reported entries but does not give complete real-time coverage for all CFB
  teams.
- Current projection corrections can publish a zero projection for reviewed
  `OUT`/`IR` designations. The new canonical state must trigger the same
  recalculation without modifying actual in-game or final fantasy points.

### Current UI and schedule

- React player card, roster, matchup, and waiver surfaces already render
  availability badges from the backend contract.
- Railway has an official-availability scheduler. The new job must reuse the
  current worker/cron approach rather than call RotoWire during a user request.

## In Scope

- A licensed, server-side RotoWire CFB API client with timeouts, retry/backoff,
  secret-safe diagnostics, payload validation, and disabled-by-default flags.
- Persistent raw provider events, sync-run observability, RotoWire provider-ID
  mappings, an unmatched queue, and a canonical availability read model.
- Deterministic status normalization, timestamp ordering, sticky negative
  statuses, manual overrides, and safe shadow mode.
- Immediate projection/cache invalidation when canonical availability changes;
  `OUT`, `SUSPENDED`, `NOT_AVAILABLE`, and `SEASON_OUT` yield a zero effective
  projection for a future game.
- Admin-only status inspection, manual sync, unmatched-event review, and
  bounded manual override APIs.
- Existing React status consumers will receive a normalized availability
  contract; no provider API key, raw payload, or unlicensed editorial text is
  exposed to browser code.

## Out of Scope

- Scraping RotoWire public HTML or treating a RotoWire absence as a status.
- Replacing completed-game fantasy points.
- Republishing RotoWire Analysis/Notes until the license explicitly permits
  public display.
- A separate scheduler framework or new Redis dependency.

## User Stories

1. As a fantasy manager, I see a clear O/Q/D/GTD designation and a realistic
   effective projection before making a lineup decision.
2. As an admin, I can audit an availability change, its source, timestamp, and
   matching confidence, and safely override it for a bounded period.
3. As an operator, I can see that the RotoWire feed is stale before users are
   shown an implied healthy status.

## Required Workflow

1. Poll RotoWire in a background worker only.
2. Store a deduplicated raw event first.
3. Resolve identity in this order: exact `SportDataIOId`, verified RotoWire ID,
   exact normalized name/team/position, controlled aliases, then unmatched
   review. Do not auto-match ambiguous identities.
4. Normalize structured injury status. Blank/unknown data produces no healthy
   transition. An unrecognized structured code is recorded as `UNKNOWN` and
   surfaced to admins.
5. Compare provider timestamp, source priority, and active manual override.
6. Persist a canonical availability assertion only when it is newer and allowed
   to supersede the current assertion.
7. Recalculate only future-game projection and matchup effects; invalidate
   read caches and emit an internal availability-change event.

## Status Rules

| Source status | Canonical status | Effective projection |
| --- | --- | --- |
| `ACT` | `AVAILABLE` | normal |
| `OUT`, `IR`, `IR-R`, `PUP` | `OUT` | 0 |
| `SUSP` | `SUSPENDED` | 0 |
| `GTD` | `GAME_TIME_DECISION` | configurable reduced probability |
| `Q` | `QUESTIONABLE` | configurable reduced probability |
| `D` | `DOUBTFUL` | configurable reduced probability |
| `NA` | `NOT_AVAILABLE` | 0 |
| `DNP` | postgame information only | no future-status inference |
| blank/missing/failed request | no status transition | retain prior status |

## API and UI Contract

- Existing player-card and league player responses continue exposing
  `injury_status`; their value is sourced from canonical availability rather
  than only the current weekly `injuries` row.
- Add admin-only `/admin/data/rotowire` endpoints for feed health, sync,
  unmatched events, player inspector, and manual overrides.
- Public responses expose derived status, source attribution, and timestamp
  only when licensing permits. They never expose API keys, provider IDs, raw
  payloads, or restricted editorial copy.

## Rollout

1. Deploy with all RotoWire writes in shadow mode.
2. Poll, persist, resolve, and report discrepancies for one live slate.
3. Review unmatched events, status conflicts, staleness, and Ahmad Hardy-style
   fixtures.
4. Enable canonical writes using a Railway environment flag; no redeploy is
   required to roll back by disabling that flag.

## Acceptance Criteria

- Missing news, blank status, empty payload, and network failure never clear a
  prior negative availability designation.
- An `OUT` player has a 0.0 effective future-game projection across player,
  roster, waiver, matchup, and win-probability reads.
- A provider event cannot overwrite a newer event or active manual override.
- Provider events are unique by provider event ID and retain an audit trail.
- Ambiguous identities enter the unmatched queue rather than changing a player.
- Stale normal-day and game-day feed conditions are visible to admins.
- No RotoWire call occurs within a public/user-facing request path.
- Existing game scoring remains authoritative after kickoff and final.
- Tests cover blank/missing news, stale ordering, manual override, matching,
  zero projection, completed-game safety, retries, and secret-safe logging.
