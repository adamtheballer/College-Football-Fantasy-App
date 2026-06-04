# Feature: End-to-End and Contract Test Coverage

## Summary

The app has grown into a stateful product with real authentication, league creation, invite joins, workspace reads, persisted draft picks, roster transactions, watchlists, and notification preferences. The current automated coverage does not match that risk. We need a deliberate test strategy across UI workflows, API contracts, and mutation-heavy backend rules so regressions are caught before they land.

This story defines the workflows that need coverage, the test layers to add, and the structure for building a maintainable test suite.

## Problem

Current coverage is materially below the product surface:

- Backend tests: [tests/api/test_health.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/tests/api/test_health.py) and [tests/api/test_leagues.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/tests/api/test_leagues.py)
- Frontend tests: only [utils.spec.ts](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/web/client/lib/utils.spec.ts)
- No browser workflow suite
- No component or hook coverage for auth, league flows, drafting, watchlists, roster management, or settings
- No broad API contract coverage for auth, join flows, notifications, watchlists, rosters, transactions, or draft mutation edge cases

Recent regressions prove this gap is real:

- Create League wizard rendered, but the CTA did not advance because an overlay intercepted clicks
- Roster selection looked disabled even though the user had access
- Enter Draft Room did not reliably take the user into the live draft room
- Invite-link and environment-specific route issues shipped into the UI

Those are exactly the kind of failures that browser and contract tests should catch.

## Goal

Add a layered automated test suite that protects the supported product surface:

- Browser workflow tests for critical user journeys
- Frontend component and hook tests for state orchestration and protected routing
- Backend API contract tests for authorization, mutation rules, and persistence

The goal is not generic coverage percentage. The goal is protecting the workflows that matter to this app.

## Current Product Surface To Cover

### Frontend routes

Supported routes in [web/client/App.tsx](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/web/client/App.tsx):

- `/`
- `/leagues`
- `/leagues/create`
- `/leagues/join`
- `/join/:inviteCode`
- `/league/:leagueId`
- `/league/:leagueId/lobby`
- `/league/:leagueId/draft`
- `/rosters`
- `/waivers`
- `/watchlists`
- `/alerts`
- `/stats`
- `/stats/players`
- `/settings`
- `/login`
- `/signup`

### Backend routes

Critical backend route groups:

- Auth: [auth.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/auth.py)
- Leagues and workspace: [leagues.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/leagues.py)
- Teams and rosters: [rosters.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/rosters.py), [teams.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/teams.py)
- Watchlists: [watchlists.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/watchlists.py)
- Notifications: [notifications.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/notifications.py)
- Players and stats: [players.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/players.py), [injuries.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/injuries.py), [schedule.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/schedule.py), [stats.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/stats.py), [projections.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/api/app/api/routes/projections.py)

## Test Strategy

### Layer 1: Browser workflow tests

Use Playwright against the running local stack. This layer protects the supported product experience and catches integration regressions, CSS overlays intercepting clicks, bad navigation, broken auth bootstrap, route mismatches, and stale UI assumptions.

### Layer 2: Frontend component and hook tests

Use Vitest plus React Testing Library for:

- protected-route behavior
- query/mutation hooks
- form validation and error states
- component states that do not need a full browser

### Layer 3: Backend contract and rule tests

Use pytest plus FastAPI `TestClient` and the existing in-memory test DB pattern from [tests/conftest.py](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/tests/conftest.py) for:

- authorization and ownership rules
- persistence after mutations
- edge cases and negative cases
- contract stability for response payloads

## Prioritized Workflow Coverage

### Critical

These are release-blocking workflows. They need browser coverage and backend coverage.

#### 1. Authentication bootstrap

UI coverage:

- sign up succeeds and lands in an authenticated state
- login succeeds and protected routes become available
- invalid login shows the correct error state
- protected route redirects unauthenticated users to `/login`
- after login, user returns to the intended protected route
- logout clears the session and returns to an unauthenticated state
- refresh/reload preserves the logged-in session when token storage is valid

Backend coverage:

- `POST /auth/signup` creates a user and returns auth payload
- duplicate email returns `409`
- `POST /auth/login` accepts valid credentials and rejects invalid credentials with `401`

#### 2. Create League wizard

UI coverage:

- authenticated user can complete the full 4-step wizard in [CreateLeague.tsx](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/web/client/pages/CreateLeague.tsx)
- clicking `Continue` advances each step
- the final submit succeeds
- success screen renders invite code and invite link
- created league appears in the leagues list
- refresh after creation still shows the created league

Backend coverage:

- `POST /leagues` creates league, settings, draft, membership, invite, and commissioner-owned team
- `POST /leagues/create` legacy alias remains covered until deliberately removed
- response contains stable shapes for `league`, `settings`, and `draft`
- unauthorized create attempt returns `401`

#### 3. Invite preview and join league

UI coverage:

- user can preview a league by invite code in [JoinLeague.tsx](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/web/client/pages/JoinLeague.tsx)
- user can join from `/leagues/join`
- user can join from `/join/:inviteCode`
- invalid invite code shows an error
- full league disables join and shows the correct message
- successful join lands on the league hub

Backend coverage:

- `POST /leagues/join-by-code` returns preview for valid code
- invalid invite returns `404` or documented error
- `POST /leagues/{league_id}/join` creates member and team
- duplicate join is rejected
- full league is rejected
- joining a private league requires valid invite path

#### 4. League hub workspace

UI coverage:

- `/league/:leagueId` loads workspace for a real member
- invalid league id shows invalid-id state
- non-member sees the correct access error
- workspace shows league metadata, owned team, standings summary, and matchup summary when data exists
- draft-lobby navigation works

Backend coverage:

- `GET /leagues/{league_id}/workspace` enforces membership
- workspace payload includes allowed actions, membership, owned team, roster, standings summary, and matchup summary
- empty-state payloads are stable when roster, standings, or matchup data is absent

#### 5. Draft lobby and persisted draft room

UI coverage:

- lobby loads from [DraftLobby.tsx](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/web/client/pages/DraftLobby.tsx)
- `Enter Draft Room` navigates into `/league/:leagueId/draft`
- draft room loads available players and current state from the API
- eligible user can save a pick
- saved pick appears in recent picks and personal picks immediately
- page reload preserves the saved pick
- ineligible user sees the restricted state and cannot save a pick

Backend coverage:

- `GET /leagues/{league_id}/draft-room` enforces membership
- `POST /leagues/{league_id}/draft-picks` persists draft picks
- saved pick also creates roster entry for the drafting team
- already drafted player cannot be drafted again
- user who is not on the clock and is not commissioner cannot save next pick
- draft-room state advances correctly after each pick

### High

These are real supported workflows and should be covered once the critical set exists.

#### 6. Roster browsing and team roster reads

UI coverage:

- `/rosters` loads joined leagues
- selecting a league updates the active roster section
- active league card is visibly selected, not faded as disabled
- empty roster state renders clearly when team has no entries
- roster cards link back to the league hub

Backend coverage:

- `GET /leagues/{league_id}/teams` enforces membership
- `GET /teams/{team_id}/roster` enforces team membership
- non-members and wrong-team access return `403`

#### 7. Waiver wire and add/drop

UI coverage:

- `/waivers` loads backend players
- filtering by position, search, and sort works
- league selector changes available-player results
- player detail modal opens
- add/drop dialog opens for an owned team with a roster
- successful add/drop updates the roster and invalidates visible state
- failure paths show destructive toast or inline error

Backend coverage:

- `POST /teams/{team_id}/add-drop` enforces owner access
- add/drop rejects when added player is already on a league roster
- add/drop rejects when dropped roster entry is invalid
- transaction row is recorded
- team roster reflects the mutation after success
- `GET /leagues/{league_id}/transactions` returns the new transaction

#### 8. Watchlists

UI coverage:

- `/watchlists` loads persisted user watchlists
- create watchlist succeeds
- rename watchlist succeeds if supported in UI
- add player to watchlist persists
- remove player from watchlist persists
- refresh keeps the updated state
- league-specific filtering works when a league context is selected

Backend coverage:

- `GET /watchlists` returns only current user watchlists
- `POST /watchlists` creates user-owned watchlist
- `PATCH /watchlists/{watchlist_id}` enforces ownership
- `POST /watchlists/{watchlist_id}/players` rejects missing players and ignores duplicates safely
- `DELETE /watchlists/{watchlist_id}/players/{player_id}` enforces ownership

#### 9. Notification preferences and alerts

UI coverage:

- `/settings` loads notification preferences
- settings save succeeds and persists after refresh
- league preference toggles persist
- `/alerts` empty state renders when there are no alerts
- test alert path or seeded alerts render in the list

Backend coverage:

- `GET /notifications/preferences` resolves to current user, not arbitrary client user key
- `POST /notifications/preferences` persists preference changes
- `GET /notifications/league-preferences` returns league-scoped rows for current user
- `POST /notifications/league-preferences` updates scoped preferences
- `GET /notifications/alerts` filters alerts by rostered players and preferences

#### 10. Player research and stats pages

UI coverage:

- players list loads in waivers/watchlists/stats flows
- player detail modal renders seeded headshot, school, and stats
- `/stats` tabs and filters load without crashing
- empty and error states render correctly for missing data

Backend coverage:

- `GET /players` supports search, sort, availability, position, and league filters
- `GET /players/{player_id}` returns stable player payload including `image_url`
- `GET /players/{player_id}/stats` returns seeded stat rows
- `GET /injuries` and `GET /injuries/player/{player_id}` return stable list/detail shapes
- `GET /stats/*`, `GET /projections*`, and `GET /schedule/player/{player_id}` return valid payloads for populated and empty datasets

### Medium

These are not as immediately risky as the above, but still belong in the suite.

#### 11. League settings and commissioner actions

Backend coverage:

- `PATCH /leagues/{league_id}/settings` commissioner-only
- `PATCH /leagues/{league_id}/draft` commissioner-only
- `POST /leagues/{league_id}/regenerate-invite` commissioner-only
- `DELETE /leagues/{league_id}` commissioner-only

UI coverage:

- commissioner sees relevant actions in workspace
- non-commissioner does not get working access to commissioner actions

#### 12. Manual roster entry and lineup updates

Backend coverage:

- `POST /teams/{team_id}/roster`
- `DELETE /teams/{team_id}/roster/{roster_entry_id}`
- `PATCH /teams/{team_id}/lineup`
- slot-limit and duplicate-entry validations

UI coverage:

- add once a supported lineup editor exists

#### 13. Defensive routing and error boundaries

UI coverage:

- invalid league ids
- expired or malformed invite codes
- API 401 recovery flow
- API 403 messaging
- network failure states on auth, league list, workspace, and draft room
- `*` route not found page

## Suggested Test Architecture

### Browser tests

Add Playwright to `web/` and create end-to-end specs for the critical flows first.

Suggested layout:

- `web/e2e/auth.spec.ts`
- `web/e2e/create-league.spec.ts`
- `web/e2e/join-league.spec.ts`
- `web/e2e/workspace.spec.ts`
- `web/e2e/draft-room.spec.ts`
- `web/e2e/rosters.spec.ts`
- `web/e2e/waivers.spec.ts`
- `web/e2e/watchlists.spec.ts`
- `web/e2e/settings-and-alerts.spec.ts`

Key requirement:

- browser tests should run against a repeatable seeded local stack and create isolated test users/leagues per test file

### Frontend component and hook tests

Add React Testing Library and target stateful logic that is cheaper than full Playwright:

- `use-auth`
- protected-route redirect logic
- create-league step transitions
- join-league preview/join state handling
- roster selection state
- draft room mutation state and disabled states
- watchlist mutation flows

Suggested layout:

- `web/client/hooks/__tests__/use-auth.spec.tsx`
- `web/client/hooks/__tests__/use-draft.spec.tsx`
- `web/client/hooks/__tests__/use-watchlists.spec.tsx`
- `web/client/hooks/__tests__/use-roster-actions.spec.tsx`
- `web/client/pages/__tests__/CreateLeague.spec.tsx`
- `web/client/pages/__tests__/JoinLeague.spec.tsx`
- `web/client/pages/__tests__/Rosters.spec.tsx`

Mocking approach:

- prefer MSW for frontend network mocking instead of ad hoc fetch stubs

### Backend API tests

Expand pytest coverage by route group and rule set.

Suggested layout:

- `tests/api/test_auth.py`
- `tests/api/test_join_league.py`
- `tests/api/test_workspace.py`
- `tests/api/test_draft_room.py`
- `tests/api/test_rosters.py`
- `tests/api/test_transactions.py`
- `tests/api/test_watchlists.py`
- `tests/api/test_notifications.py`
- `tests/api/test_players.py`
- `tests/api/test_stats.py`
- `tests/api/test_commissioner_actions.py`

Fixture work to add:

- user factory
- auth-header helper
- league factory
- team factory
- roster-entry factory
- player factory
- watchlist factory
- draft state factory

## Implementation Notes

- Keep browser tests narrow and deterministic. Avoid one giant “everything” spec.
- Prefer asserting product outcomes, not internal CSS structure.
- Seed backend state through factories or direct API setup, not through manual SQL fixtures checked into tests.
- Use the committed seed data only when the test needs realistic player inventory. Most tests should still build the minimum state needed.
- Standardize helper commands so CI and developers run the same suite shape.
- Split fast local feedback from slower browser suites:
  - `pytest` for backend contracts
  - `npm --prefix web test` for component and hook tests
  - `npm --prefix web run test:e2e` for browser workflows

## Acceptance Criteria

- A browser test harness exists and runs at least the Critical workflow set
- Frontend unit/integration tests exist for protected routing and core mutation hooks
- Backend contract tests cover auth, create/join league, workspace, draft-room persistence, roster mutations, watchlists, and notifications
- Test helpers/factories make it easy to set up league, team, roster, player, and draft state
- Regression cases already seen in this repo are protected by automation:
  - create-league button blocked by overlay
  - roster selection appears disabled or does not visibly select
  - draft lobby CTA fails to enter the draft room
  - saved draft pick does not persist after reload
- README or developer docs include how to run backend tests, frontend tests, and browser tests

## Out of Scope

- Snapshot-based visual testing for every page
- Performance benchmarking
- Replacing all current fixtures with full production-like seed loads
- Third-party provider integration tests against live SportsDataIO or other external APIs

## Recommended Rollout

1. Add Playwright and backend factory helpers
2. Cover auth, create league, join league, workspace, and draft room first
3. Add roster, waivers, watchlists, and settings/alerts coverage
4. Expand backend contract tests to commissioner actions, stats, and defensive edge cases
5. Wire the critical suites into CI so merges are blocked on failures
