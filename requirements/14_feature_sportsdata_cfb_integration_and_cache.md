# Feature: SportsDataIO NCAA Football Integration with Cached Database Backing

## Description
Build a real backend integration against SportsDataIO's NCAA Football API so the app can source college football reference data, schedules, standings, injuries, and stats from one provider-backed pipeline, while using Postgres as the canonical operating store and cache.

This story is explicitly designed for the SportsDataIO free trial / low-call environment first. The implementation must minimize provider calls, store normalized data in the app database, and refresh provider feeds only when a feed-level cache entry is expired or missing.

## Why This Story Exists
The current backend has partial, inconsistent provider usage:

- `SportsDataClient` only supports direct player stat lookups and weekly player-game stats ingestion.
- `players.external_id` exists, but there is no systematic SportsDataIO roster/team/schedule sync.
- `player_stats`, `player_game_stats`, and `team_game_stats` exist, but only `player_stats` is actively used.
- team stats, standings, and schedules are still split across CFBD and ESPN-based flows.
- injuries come from Rotowire, not SportsDataIO.
- there is no provider cache control layer, no feed expiry policy, and no sync-state tracking.

That leaves the app with provider drift, fragile refresh behavior, and no clean way to scale the SportsData integration without wasting calls.

## Provider Constraints We Must Design Around
- SportsDataIO's free trial uses scrambled data for scores and stats, while teams, players, schedules, and IDs remain accurate enough for integration work.
- SportsDataIO states that the free trial is limited to `1,000 API calls/mo`.
- SportsDataIO recommends syncing reference feeds into your own database and using `Box Scores by Week` as the primary stats integration feed for team sports.
- SportsDataIO does **not** provide college sports depth charts or lineup feeds.
- College Football headshots are a separate partner integration, not a standard NCAA Football core endpoint.

## In Scope
- Add a provider-backed SportsDataIO data domain for NCAA Football
- Define the canonical SportsData feed set this app will use in v1
- Store provider-backed data in Postgres and serve app reads from the database
- Add feed-level cache expiry and sync-state tracking
- Make feed expiry configurable in backend app settings
- Replace per-request provider lookups with on-demand feed refresh plus DB-backed reads
- Plan migration from the current mixed-source stats/schedule/injury stack toward SportsDataIO-backed data where appropriate
- Publish the implementation plan, schema plan, and mapping plan in one GitHub issue

## Out of Scope
- Paying for a SportsDataIO production plan right now
- Websocket/live delta sync for every game state change
- Replacing every existing projection algorithm in this story
- Solving depth chart / starting lineup ingestion through SportsDataIO, because their college football feeds do not provide it
- Licensed headshot ingestion through SportsDataIO's image partners in v1

## Current State Analysis

### Existing SportsDataIO usage
- `api/app/integrations/sportsdata.py`
  - supports:
    - `stats/json/Player/{external_id}`
    - `stats/json/PlayerGameStatsByWeek/{season}/{week}`
- `scripts/ingest_sportsdata_player_stats.py`
  - bulk-imports `PlayerGameStatsByWeek`
  - upserts into `player_stats`

### Existing models relevant to this project
- `api/app/models/player.py`
  - has `external_id`
  - currently acts as the only SportsDataIO linkage point
- `api/app/models/player_stat.py`
  - `(player_id, season, week)` JSON stat cache
- `api/app/models/player_game_stat.py`
  - game-level player stat table exists but is not the active canonical path
- `api/app/models/team_game_stat.py`
  - game-level team stat table exists but is not the active canonical path
- `api/app/models/team_stats_snapshot.py`
  - currently used for season-level team stats snapshots, largely CFBD-backed
- `api/app/models/game.py`
  - usable schedule/game dimension table with `external_id`
- `api/app/models/injury.py`
  - current injury persistence target

### Key architectural gaps
- no feed sync state table
- no `expires_at` tracking by feed scope
- no call-budget-aware integration path
- no explicit SportsData team IDs on team-like entities
- no consistent rule for whether `player_stats` or `player_game_stats` is canonical
- no on-demand refresh orchestration based on cache staleness
- secrets/config hygiene issue:
  - `.env.example` currently includes a literal `SPORTSDATA_API_KEY` value and should not

## Recommended SportsDataIO Feed Set for V1
Use the following SportsDataIO NCAA Football feed families as the planned provider surface.

### 1. Reference / competition data
- Teams
- Players / Rosters
- Regular Season Standings
- Postseason Standings
- Schedules & Gameday Info

### 2. Stats data
- `CFB Box Scores by Week`
  - recommended by SportsDataIO as the primary way to sync team and player stats
  - should be preferred over per-player lookups because one call hydrates game, player, and team stat data together

### 3. Optional pregame enhancement feeds
- Projected Player Game Stats by Week
  - use only if the selected free-trial package actually exposes it
  - must be treated as optional behind config / feature flags

### 4. Injuries
- SportsDataIO college football injury feed(s)
  - use as the canonical structured injury source if accessible on the current plan
  - otherwise preserve Rotowire as fallback until SportsDataIO access is confirmed

### Explicitly not part of the SportsDataIO v1 source plan
- Depth charts / starting lineups for college football
  - SportsDataIO says these are not provided for college sports
- Headshots
  - SportsDataIO's workflow guide says CFB headshots are available through a separate partner integration

## Call Budget Strategy for the Free Trial
We should optimize for `bulk feed refresh + database reads`, not `request-time direct provider calls`.

### Rules
- Never call SportsDataIO per player request when a week-level or season-level bulk feed exists.
- Prefer refreshing one feed for a `(season, week)` scope and then serving many app requests from DB.
- Default all SportsData feeds to a configurable 30-day TTL in v1 to stay within the free-trial call budget.
- Store `expires_at` for each synced feed scope in the database.
- Allow future per-feed TTL overrides without schema redesign.

### Example low-call policy
- Teams / rosters: refresh every 30 days
- Schedule: refresh every 30 days
- Standings: refresh every 30 days in v1
- Box scores for a given `(season, week)`: refresh once every 30 days in v1
- Injuries: refresh every 30 days in v1 unless product needs force a shorter interval later

### Important note
This is intentionally conservative for the free trial. It is not the ideal cadence for a live fantasy product, but it is the correct initial architecture because it preserves the right sync boundaries and avoids rewriting the system later.

## Proposed Backend Configuration
Add provider settings to `api/app/core/config.py` and document them in `.env.example`.

### Required settings
- `SPORTSDATA_API_KEY`
- `SPORTSDATA_BASE_URL`
- `SPORTSDATA_ENABLED=true|false`
- `SPORTSDATA_CACHE_TTL_DAYS=30`

### Recommended future-ready feed overrides
- `SPORTSDATA_REFERENCE_TTL_DAYS=30`
- `SPORTSDATA_SCHEDULE_TTL_DAYS=30`
- `SPORTSDATA_STANDINGS_TTL_DAYS=30`
- `SPORTSDATA_BOXSCORE_TTL_DAYS=30`
- `SPORTSDATA_INJURY_TTL_DAYS=30`
- `SPORTSDATA_PROJECTION_TTL_DAYS=30`

### Secret hygiene requirement
- remove the literal SportsData key from `.env.example`
- leave the key blank and document how to set it locally

## Proposed Schema Changes

### A. Add provider sync-state tracking
Create a new table, recommended name: `provider_sync_states`

Suggested columns:
- `id`
- `provider` (`sportsdata`)
- `feed`
  - examples:
    - `teams`
    - `players`
    - `schedule`
    - `standings_regular`
    - `standings_postseason`
    - `box_scores_week`
    - `injuries`
    - `projected_player_game_stats_week`
- `scope_key`
  - examples:
    - `2026`
    - `2026:week:4`
    - `2026:postseason`
- `season`
- `week`
- `status`
  - `pending`
  - `success`
  - `error`
- `last_started_at`
- `last_succeeded_at`
- `expires_at`
- `last_error`
- `request_count`
- `meta_json`

Why:
- this is the core cache coordinator
- lets read paths decide whether a refresh is needed without guessing from domain rows
- allows future per-feed TTL changes without rewriting downstream tables

### B. Strengthen provider identity columns
Current generic `external_id` fields are not enough if this app continues to use multiple providers.

Recommended additions:
- `players.sportsdata_player_id`
- `players.sportsdata_team_id` or `players.current_team_key`
- `games.sportsdata_game_id`
- optional future `teams` domain table or `sportsdata_teams` dimension with:
  - `sportsdata_team_id`
  - `key`
  - `school`
  - `short_display_name`
  - `conference`

If we want minimum churn, we can keep current `external_id` temporarily and document that it means `sportsdata_player_id`, but the cleaner architecture is explicit provider columns.

### C. Make game-level stats canonical
The app already has:
- `player_game_stats`
- `team_game_stats`

Recommendation:
- make these the canonical provider-backed stats store from `Box Scores by Week`
- continue serving existing app needs through materialized or derived views/tables such as:
  - `player_stats`
  - `team_stats_snapshots`

This avoids duplicated provider calls and gives us a clean audit trail by game.

### D. Keep aggregate/snapshot tables as app-facing projections
Keep using:
- `player_stats`
- `team_stats_snapshots`
- `injuries`

But define them as app-facing derived caches, not the only source of truth.

### E. Optional raw payload table
Optional table for debugging and replay:
- `provider_raw_payloads`
  - `provider`
  - `feed`
  - `scope_key`
  - `payload_json`
  - `fetched_at`

This is useful but not required for v1. If omitted, `provider_sync_states.meta_json` should still capture enough metadata for observability.

## Data Mapping Plan

### Teams / rosters
Map SportsDataIO team and roster feeds into:
- `players`
  - name
  - sportsdata player id
  - position
  - current school / team
  - jersey, class year, height, weight, hometown if we choose to enrich schema

Recommended app additions to `players`:
- `jersey_number`
- `class_year`
- `height`
- `weight`
- `hometown`
- `is_active`

### Schedule / games
Map SportsDataIO schedule feeds into `games`
- SportsData `GameID` -> `games.sportsdata_game_id` or `external_id`
- `season`, `week`, `season_type`
- `DateTime` -> `start_date`
- `Status`
- home / away teams
- neutral site
- scores if present

### Player game stats
Map `Box Scores by Week` player rows into `player_game_stats`
- foreign keys:
  - player
  - game
- season / week
- raw provider stat JSON
- source = `sportsdata`

### Team game stats
Map `Box Scores by Week` team rows into `team_game_stats`
- team identity
- game
- season / week
- raw provider stat JSON
- source = `sportsdata`

### Player season / weekly aggregate stats
Compatibility plan:
- continue exposing `GET /players/:player_id/stats`
- when a request asks for a given `(season, week)`:
  - check the sync state for `box_scores_week`
  - if expired or missing, refresh `Box Scores by Week`
  - read normalized output from DB
- for season totals:
  - use `week = 0` convention in `player_stats`
  - derive from season feed or aggregate game-level rows

### Team stats snapshots
Populate or refresh `team_stats_snapshots` from SportsDataIO season / game-level data
- move source from CFBD/ESPN toward `sportsdata`
- store offense/defense/advanced stats only for fields we actually use in the app

### Injuries
If SportsDataIO college injuries are available on the current free plan:
- map to existing `injuries` table:
  - `InjuryStatus` -> `status`
  - `InjuryBodyPart` -> `injury`
  - `InjuryNotes` -> `notes`
  - `InjuryStartDate` -> date metadata if schema is extended

Recommended schema additions to `injuries`:
- `source_updated_at`
- `body_part`
- `injury_start_date`
- `provider_status_raw`

### Standings
Use SportsDataIO standings as a provider-backed standings source for public stats pages.
- do not confuse provider standings with fantasy league standings
- provider standings should feed team research pages, not fantasy league `standings`

## Recommended Service Architecture

### 1. Provider client layer
New or expanded module:
- `api/app/integrations/sportsdata.py`

Responsibilities:
- typed endpoint wrappers
- provider auth
- request errors
- endpoint path constants

### 2. Feed sync services
New modules:
- `api/app/services/providers/sportsdata_reference.py`
- `api/app/services/providers/sportsdata_schedule.py`
- `api/app/services/providers/sportsdata_boxscores.py`
- `api/app/services/providers/sportsdata_injuries.py`
- optional:
  - `api/app/services/providers/sportsdata_projections.py`

Responsibilities:
- fetch provider feed
- map response to domain rows
- upsert DB records
- update `provider_sync_states`

### 3. Cache coordinator
New module:
- `api/app/services/providers/cache_policy.py`

Responsibilities:
- compute TTL from app settings
- determine if feed scope is stale
- prevent repeated refresh storms
- expose `ensure_feed_fresh(provider, feed, scope)`

### 4. App-facing query services
New modules:
- `api/app/services/player_stats_service.py`
- `api/app/services/team_stats_service.py`
- `api/app/services/injury_service.py`

Responsibilities:
- serve API routes from DB
- trigger lazy refresh only when cache expired or missing
- never let route handlers know provider endpoint details

## Endpoint Plan for Our Backend

### Routes that should become DB-first with lazy SportsData refresh
- `GET /players`
- `GET /players/:player_id`
- `GET /players/:player_id/stats`
- `GET /injuries`
- `GET /injuries/:player_id`
- `GET /stats/teams`
- `GET /stats/team/:team_name`
- `GET /stats/standings`
- `GET /schedule/...`

### Internal refresh pattern
Example for `GET /players/:player_id/stats?season=2026&week=4`
1. route calls service
2. service checks `provider_sync_states` for `sportsdata / box_scores_week / 2026:4`
3. if missing or expired:
   - fetch `CFB Box Scores by Week`
   - upsert `games`, `player_game_stats`, `team_game_stats`
   - update derived `player_stats`
   - set `expires_at = now + ttl`
4. serve response from DB

This pattern is the key requirement of the story.

## Acceptance Criteria
- The backend has a documented SportsDataIO NCAA Football integration plan using Postgres as the canonical operating store.
- Feed expiry is configurable in backend app settings and defaults to 30 days in v1.
- The backend can decide whether to refresh a provider feed based on database-stored `expires_at`, not ad hoc request logic.
- Box-score or other bulk feeds are used for stat synchronization instead of per-player provider requests wherever possible.
- Existing stats routes are served from database-backed records, with lazy refresh only when feed scope is stale.
- Provider sync state is visible and auditable for each feed scope.
- The design explicitly handles SportsDataIO free-trial constraints:
  - scrambled stats
  - 1,000 API calls per month
  - some endpoints unavailable
- The issue documents what SportsDataIO can and cannot supply for college football:
  - yes: teams, players, schedules, standings, injuries, stats
  - no: depth charts / lineups
  - headshots: separate partner path, not standard v1
- `.env.example` no longer contains a real SportsData key value.

## Implementation Phases

### Phase 1: Provider foundation
- expand SportsData client
- add provider sync-state table
- add TTL config in settings
- remove committed key from `.env.example`

### Phase 2: Reference + schedule sync
- implement teams/players/schedule/standings sync services
- store provider IDs cleanly
- add CLI scripts for manual sync

### Phase 3: Stats sync
- implement `Box Scores by Week` ingestion
- make `player_game_stats` and `team_game_stats` canonical
- derive or refresh `player_stats`

### Phase 4: Injuries
- add SportsDataIO injury sync if feed access is available
- otherwise keep Rotowire fallback behind a provider switch

### Phase 5: Route migration
- move player/stats/schedule routes onto DB-first provider-backed services
- add tests for stale-cache refresh behavior

## Suggested CLI / Script Surface
- `scripts/sync_sportsdata_reference.py --season 2026`
- `scripts/sync_sportsdata_schedule.py --season 2026`
- `scripts/sync_sportsdata_boxscores.py --season 2026 --week 4`
- `scripts/sync_sportsdata_injuries.py --season 2026 --week 4`
- `scripts/refresh_stale_sportsdata_feeds.py`

## Testing Requirements
- unit tests for cache-policy decisions
- API tests for lazy refresh path
- API tests for cache-hit path with no provider call
- integration tests for mapping:
  - teams
  - players
  - games
  - player game stats
  - team game stats
- test that repeat calls within TTL do not re-hit provider
- test that expired feed scopes do refresh
- test that free-trial scrambled stats are still stored and surfaced structurally

## Open Questions / Decisions to Make During Implementation
- Should we keep `external_id` generic or add explicit `sportsdata_*` identity columns now?
- Should `player_stats` remain a first-class table or become a derived/materialized compatibility cache over `player_game_stats`?
- Is SportsDataIO injury access available in the chosen free-trial setup?
- Do we want one global TTL in v1, or config-ready per-feed TTLs from day one?

## Source Notes
- SportsDataIO NCAA Football workflow guide:
  - teams/rosters, schedule, standings, stats, injuries, and no depth charts
  - https://sportsdata.io/developers/workflow-guide/ncaa-football
- SportsDataIO implementation guide:
  - recommends syncing box scores as the core stats feed
  - https://support.sportsdata.io/hc/en-us/articles/4406143209367-Sports-Data-API-Implementation-Guide
- SportsDataIO introduction/testing:
  - free trial uses scrambled data
  - https://sportsdata.io/developers/apis
- SportsDataIO scrambled data / admin notes:
  - scores and stats are scrambled on the free plan
  - free trial budget is 1,000 API calls per month
  - https://sportsdata.io/help/scrambled-data
