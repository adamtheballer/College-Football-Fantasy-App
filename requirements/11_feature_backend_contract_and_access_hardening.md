# Feature: Backend Contract and Access Hardening

## Description
Harden the backend so the API exposes one canonical league contract, enforces league ownership and roster invariants, and moves orchestration logic out of route handlers into stable domain services.

## In Scope
- Canonicalize league creation and league detail contracts
- Enforce authentication, membership, commissioner, and team ownership on league-domain routes
- Enforce league-scoped roster and team invariants
- Add a backend-facing league workspace contract for the React UI
- Refactor large route handlers into domain services and query services
- Migrate notification identity and delivery flow away from string `user_key`
- Update tests, Bruno requests, and docs to the canonical contracts

## Out of Scope
- Rebuilding every analytics or stats algorithm
- Introducing third-party auth providers
- Replacing all scheduled jobs with a separate queueing platform in this story

## User Stories
- As a user, I can only view and mutate leagues, teams, and rosters that I belong to or own.
- As a commissioner, I can manage league settings and invites without exposing those actions to non-members.
- As an engineer, I can rely on one league API contract across UI, tests, and API workflow tooling.

## Acceptance Criteria
- All mutating league, team, roster, and notification preference endpoints derive identity from auth headers, not request payload fields.
- League detail, member list, settings update, invite regeneration, draft reschedule, and delete paths enforce commissioner or membership scope as appropriate.
- Team and roster writes enforce league-domain rules:
  - one owned team per user per league
  - no duplicate rostering of the same player across teams in the same league
  - roster slot and league capacity validation is applied consistently
- Canonical league creation uses `POST /leagues` with the workflow payload currently used by create league.
- Legacy league creation aliases are removed or deprecated behind a documented compatibility window.
- Route handlers delegate orchestration to service modules for league lifecycle, notifications, and analytics queries.
- Notification persistence uses explicit user identifiers and supports attempt tracking for scheduled deliveries.
- Backend tests validate the canonical contracts and authorization boundaries.

## Workflow
1. Define the canonical league API surface and publish it in schemas, tests, and Bruno collections.
2. Introduce auth scope helpers for membership, commissioner, and team ownership.
3. Move league lifecycle logic into a dedicated service module.
4. Add league-scoped roster and team invariant enforcement in the service layer.
5. Add a single `league workspace` query contract for the React league hub.
6. Migrate notification tables and scripts from `user_key` strings to explicit user IDs and delivery attempts.
7. Move integration fallback logic behind service or integration boundaries.
8. Update tests, Bruno, and docs to the new canonical contracts.

## API Specs
- Canonical league endpoints
  - `POST /leagues`
    - Request body: current `LeagueCreateRequest`
    - Response: current `LeagueCreateResponse`
  - `GET /leagues`
    - Query params: `limit`, `offset`, optional `scope=mine|member|all`
    - Default behavior should return leagues visible to the current user for authenticated clients
  - `GET /leagues/:league_id`
    - Response: `LeagueDetailRead`
    - Visibility should be membership-scoped for private leagues
  - `GET /leagues/:league_id/workspace`
    - Response includes league, membership, owned team, roster, matchup summary, standings summary, and allowed actions
  - `POST /leagues/:league_id/join`
  - `PATCH /leagues/:league_id/settings`
  - `PATCH /leagues/:league_id/draft`
  - `POST /leagues/:league_id/regenerate-invite`
  - `DELETE /leagues/:league_id`
- Team and roster endpoints
  - `POST /leagues/:league_id/teams`
    - Requires authenticated membership and commissioner or self-team creation policy
  - `GET /leagues/:league_id/teams`
    - Membership scoped
  - `GET /teams/:team_id/roster`
    - Membership scoped
  - `POST /teams/:team_id/roster`
    - Owner scoped
  - `DELETE /teams/:team_id/roster/:roster_entry_id`
    - Owner scoped
- Notification endpoints
  - `GET /notifications/preferences`
  - `POST /notifications/preferences`
  - `GET /notifications/league-preferences`
  - `POST /notifications/league-preferences`
  - Request and response payloads must not include client-authored identity fields such as `user_key`

## UI Specs
- Backend contracts must support the React app as the primary UI
- `league workspace` must be sufficient to replace mock hydration in league detail and roster views
- Error semantics must be stable for unauthorized, forbidden, not found, validation failure, and conflict states

## Database Specs
- Table: `teams`
  - Add validation for one owned team per user per league
  - Recommended implementation:
    - additive nullable-safe unique index on `(league_id, owner_user_id)` where `owner_user_id` is not null
    - pre-migration cleanup for duplicates
- Table: `roster_entries`
  - Add league-scoped uniqueness for rostered players
  - Recommended implementation:
    - add `league_id` column as an additive migration
    - backfill from `teams.league_id`
    - add unique constraint on `(league_id, player_id)`
    - keep `team_id + player_id` uniqueness
- Notification tables
  - Add `user_id` foreign key to:
    - `push_tokens`
    - `notification_preferences`
    - `notification_logs`
    - `notification_league_preferences`
  - Backfill `user_id` from existing `user_key`
  - Keep `user_key` temporarily for compatibility, then remove it in a follow-up migration
- Optional supporting indexes
  - `league_members (user_id, league_id)`
  - `scheduled_notifications (scheduled_for, sent_at, canceled_at)`
  - `roster_entries (league_id, player_id)`

## Technical Notes
- Recommended implementation details
  - Create `api/app/services/league_flow.py` for create, join, invite, settings, draft reschedule, and delete logic
  - Create `api/app/services/league_workspace.py` for the aggregated read model used by the React league hub
  - Add dependency helpers such as:
    - `require_current_user`
    - `require_league_member`
    - `require_commissioner`
    - `require_team_owner`
  - Move notification filtering and preference resolution into a service module
  - Move provider fallback from route handlers into integration-facing services
- Contract decision
  - `POST /leagues` should become the canonical create route
  - `POST /leagues/create` should call the same service during transition and emit a deprecation note in docs/tests until removed
- Notification delivery
  - Add an outbox-style delivery table or attempt table for scheduled sends
  - Record per-channel attempt status, error message, and delivered timestamp
  - Do not mark scheduled notifications as sent until downstream delivery work finishes or a terminal state is recorded
- Config hardening
  - Move allowed CORS origins and UI base URLs fully into config
  - Support explicit environments for React production and React local development only

## Rollout Notes
- Phase 1
  - Add scope dependencies
  - Canonicalize `POST /leagues`
  - Update tests and Bruno
- Phase 2
  - Introduce `league_flow` and `league_workspace` services
  - Migrate React to the workspace contract
- Phase 3
  - Add team and roster invariant constraints with additive migrations and backfills
  - Migrate notification identity to `user_id`
- Phase 4
  - Remove deprecated route aliases and compatibility fields
- Testing
  - Add API tests for auth failures, forbidden access, league create, join, workspace read, settings update, and roster mutations
  - Add migration smoke checks for `user_id` and `roster_entries.league_id` backfills
  - Update Bruno collections to the canonical route surface
