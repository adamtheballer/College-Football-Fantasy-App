# Epic: React Frontend Delivery

## Summary
Make `web/` the only supported frontend, replace mock-backed league workflows with canonical backend contracts, and deliver the missing league management pages required for a complete in-season fantasy experience.

## In Scope
- Adopt `web/` React as the canonical UI surface
- Deprecate and remove `ui/` Streamlit from the supported user workflow
- Replace mock-backed React pages with API-backed data
- Complete the missing league hub pages and persistent roster workflows
- Deliver a persisted draft workflow for React

## Out of Scope
- Native mobile apps
- Payments, subscriptions, or premium tiers
- Full real-time websocket infrastructure beyond what is needed for draft state freshness
- Rebuilding all analytics logic that already exists behind working API endpoints

## Success Criteria
- A new user can sign up, create or join a league, navigate the React app, and complete core league workflows without touching Streamlit.
- League detail, roster, waiver, injury, alerts, trade, and stats screens use backend-backed data for supported workflows.
- Placeholder league routes are replaced with implemented React pages or are removed from supported navigation.
- Streamlit is no longer documented or started as part of normal local development.

## Story 1: React Becomes the Only Supported Frontend

### Description
Standardize the product on `web/` so navigation, requirements, and contracts no longer split across React and Streamlit.

### User Stories
- As a user, I only see one frontend path for the app.
- As an engineer, I can make UI changes in one surface without matching behavior in a second unsupported UI.
- As a reviewer, I can evaluate frontend completeness against one route map and one navigation model.

### Acceptance Criteria
- `web/` is documented as the primary and only supported frontend in `README.md`.
- Local dev scripts start the API and React app, not Streamlit.
- Supported navigation in React does not link to placeholder routes unless those routes are explicitly marked as unavailable and hidden from primary nav.
- `ui/` is either removed or clearly marked as deprecated and excluded from normal startup paths.
- Environment variable documentation and setup instructions reflect React-only frontend execution.

### Workflow
1. Mark React as the canonical frontend in requirements, docs, and run scripts.
2. Remove Streamlit startup from the supported local development workflow.
3. Audit React route definitions and sidebar/header navigation for placeholder or dead-end entries.
4. Hide, remove, or implement unsupported routes before calling the frontend complete.
5. Remove React fallback assumptions that depend on Streamlit-era navigation or docs.

### API Specs
- No new user-facing endpoints are required for this story.
- Existing API docs and examples must reference React-facing routes and payloads only.

### UI Specs
- Target surface: `web/`
- React route map must be treated as the source of truth.
- Primary navigation must include only supported workflows or clearly disabled entries with explicit unavailable messaging.
- Auth bootstrap must consistently gate authenticated pages.

### Database Specs
- No schema changes required.

### Technical Notes
- This story should be completed before deeper feature work so the team does not continue investing in duplicate UI surfaces.
- Any remaining Streamlit files should be removed only after required parity pages are available in React.

## Story 2: Replace Mock Hydration with a Canonical League Workspace

### Description
Replace local mock seeding in league, roster, waiver, injury-detail, and related pages with a single backend-backed read model and supporting research queries.

### User Stories
- As a league member, I can open a league and see my real roster, matchup context, standings, and available actions.
- As a user, I can trust that player details and waiver recommendations reflect backend data rather than demo content.
- As an engineer, I can hydrate the React league hub from one stable contract instead of page-local mock logic.

### Acceptance Criteria
- League detail no longer seeds roster or opponent data from `allPlayersMock`.
- Roster, waiver, and injury detail flows use backend responses for supported data.
- The React app has one canonical league workspace fetch for league-scoped summary data.
- Loading, empty, unauthorized, forbidden, and error states are visible and distinct on workspace-backed pages.
- Writes that change roster or league state invalidate cached workspace and dependent queries.

### Workflow
1. Define a `league workspace` contract that returns league summary, current membership, owned team, roster snapshot, matchup summary, standings summary, and allowed actions.
2. Implement a shared React query layer for workspace reads and invalidation after league writes.
3. Replace mock hydration in league detail and roster-adjacent pages with the workspace contract.
4. Update waiver and injury detail pages to resolve player detail from backend-backed player records.
5. Remove fallback-to-mock behavior from supported league views.

### API Specs
- `GET /leagues/:league_id/workspace`
  - Response should include:
    - `league`
    - `membership`
    - `owned_team`
    - `roster`
    - `matchup_summary`
    - `standings_summary`
    - `allowed_actions`
- `GET /players`
  - Must support filters needed by React waiver and injury flows:
    - `search`
    - `position`
    - `school`
    - `limit`
    - `offset`
- `GET /players/:player_id`
  - Must provide enough detail for modal/profile hydration without requiring a mock fallback.
- Existing stats, injuries, schedule, projections, and matchup endpoints remain the supporting research surface.

### UI Specs
- Target surface: `web/`
- Add shared query hooks under the React data layer for:
  - league workspace
  - players search/detail
  - roster detail
- League detail, roster, and player detail entry points must render:
  - loading
  - empty
  - not found
  - auth/permission failure
  - success
- League actions shown in the UI must be driven by `allowed_actions`, not hardcoded assumptions.

### Database Specs
- No mandatory schema change for the initial workspace read model.
- Supporting indexes may be needed for league-scoped reads if aggregation queries become slow.

### Technical Notes
- This story depends on the contract hardening work already described in [11_feature_backend_contract_and_access_hardening.md](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/requirements/11_feature_backend_contract_and_access_hardening.md).
- The React query layer should replace page-local `useEffect` fetch patterns where league-scoped caching matters.

## Story 3: Complete the React League Hub Pages

### Description
Implement the missing league hub pages so My Team, Matchup, Scoreboard, League News, and Power Rankings are real React workflows rather than placeholders.

### User Stories
- As a user, I can move between my team, this week’s matchup, scoreboard, league news, and rankings from the league hub.
- As a user, I can understand what is happening in my league without leaving the React app.
- As a commissioner or engaged manager, I can use league news and rankings to make weekly decisions.

### Acceptance Criteria
- React no longer serves placeholder components for:
  - `/my-team`
  - `/matchup`
  - `/scoreboard`
  - `/league-news`
  - `/power-rankings`
- Each page is reachable from league-aware navigation and reads the current league context.
- My Team shows roster groupings, upcoming schedule context, and recent transactions for the owned team.
- Matchup shows head-to-head starters, projections, and scoring breakdown for the current week.
- Scoreboard shows all league matchups for the selected week.
- League News shows injuries, waiver-relevant news, and notable league activity.
- Power Rankings shows a transparent ranking model with enough explanation to be interpretable.

### Workflow
1. Add a persistent league context selection or derive current league from the active workspace route.
2. Implement My Team using owned team and roster data.
3. Implement Matchup and Scoreboard using weekly matchup and scoring summary endpoints.
4. Implement League News using injuries, alerts, transactions, and league activity feeds.
5. Implement Power Rankings using standings, points, streak, and recent performance inputs.

### API Specs
- `GET /leagues/:league_id/workspace`
  - Must expose current team and matchup references for page routing.
- `GET /leagues/:league_id/matchups`
  - Required for matchup and scoreboard views
  - Query params: `week`
- `GET /leagues/:league_id/transactions`
  - Response: league activity and roster move feed
- `GET /leagues/:league_id/news`
  - Response: league-scoped curated news and injury summaries
- `GET /leagues/:league_id/power-rankings`
  - Response: ordered ranking rows and explanation fields

### UI Specs
- Target surface: `web/`
- League hub navigation should live under league-aware routes such as `/league/:leagueId/...`
- Each page must support week selection where the data model allows it.
- Matchup and Scoreboard must make scoring status obvious:
  - projected
  - live
  - final
- News and rankings pages must include empty states when a league is newly created or pre-season.

### Database Specs
- If league transactions and rankings are not already persisted, add one of:
  - cached summary tables
  - additive materialized read models
  - deterministic service queries over existing data
- If ranking snapshots are stored, include `league_id`, `week`, `rank`, and explanation fields.

### Technical Notes
- These pages should be built on league-aware routes instead of global placeholder paths once the route structure is finalized.
- Power Rankings may begin as a deterministic service output before adding persistence.

## Story 4: Deliver Persistent Roster Actions, Waivers, and Watchlists

### Description
Turn roster management from a static display into a persistent workflow with add/drop, lineup edits, waiver targeting, and saved watchlists.

### User Stories
- As a team owner, I can set starters and bench players within roster rules.
- As a team owner, I can add and drop players and see the transaction reflected in my roster and league activity.
- As a user, I can save players to watchlists and revisit them later.
- As a user, I can browse waivers using real rostered percentage, projections, and schedule context.

### Acceptance Criteria
- Users can submit lineup changes that are validated against roster-slot rules.
- Users can add a free agent and drop a rostered player through a single supported workflow.
- Add/drop and lineup changes update the roster view, workspace view, and activity feed after write completion.
- Watchlists are persisted per user and survive refresh, logout, and login.
- Waiver Wire is backed by real player and availability data, not local `playersMock`.
- Errors for invalid lineup, roster limit conflicts, player already rostered, or unauthorized action are surfaced clearly.

### Workflow
1. User opens My Team or Waiver Wire from the current league.
2. User edits lineup or starts an add/drop flow.
3. Backend validates ownership, league membership, roster limits, and player availability.
4. Successful writes update roster state, transaction history, and any relevant league activity surfaces.
5. User saves or removes players from watchlists independent of roster moves.

### API Specs
- `PATCH /teams/:team_id/lineup`
  - Request body: list of `roster_entry_id` to target slot assignments
  - Response: updated lineup snapshot
- `POST /teams/:team_id/add-drop`
  - Request body:
    - `add_player_id`
    - `drop_roster_entry_id`
    - optional `reason`
  - Response:
    - updated roster
    - created transaction summary
- `GET /players`
  - Must support league-aware availability filters:
    - `league_id`
    - `available_only`
    - `position`
    - `search`
    - `sort`
- `GET /watchlists`
  - Query params: optional `league_id`
- `POST /watchlists`
  - Request body: `name`, optional `league_id`
- `POST /watchlists/:watchlist_id/players`
  - Request body: `player_id`
- `DELETE /watchlists/:watchlist_id/players/:player_id`

### UI Specs
- Target surface: `web/`
- My Team page must support drag/drop or explicit slot actions for lineup edits.
- Waiver Wire must expose:
  - filters
  - sort options
  - player detail modal
  - add/drop action entry point
- Watchlist UI must support:
  - create watchlist
  - rename watchlist
  - add/remove player
  - view by list
- Success and failure toasts must map to actual write results, not optimistic assumptions.

### Database Specs
- Table: `roster_entries`
  - Must support slot assignment updates and transaction-safe ownership checks
- Table: `transactions`
  - Add or confirm league activity persistence for add/drop and lineup actions
  - Recommended columns:
    - `league_id`
    - `team_id`
    - `transaction_type`
    - `player_id`
    - `related_player_id`
    - `created_by_user_id`
    - `created_at`
- Table: `watchlists`
  - Columns:
    - `id`
    - `user_id`
    - `league_id` nullable
    - `name`
    - `created_at`
    - `updated_at`
- Table: `watchlist_players`
  - Columns:
    - `watchlist_id`
    - `player_id`
    - `created_at`
  - Unique constraint: `watchlist_id + player_id`

### Technical Notes
- Add/drop should be one transaction at the service layer so roster invariants remain consistent.
- Watchlists should be user-owned and not derived from local storage.

## Story 5: Deliver a Persisted React Draft Workflow

### Description
Replace the demo draft experience with a persisted league-scoped draft lobby and draft room that reflects real teams, picks, and draft status.

### User Stories
- As a commissioner, I can create, schedule, and launch a draft from the React app.
- As a manager, I can enter the draft room, see the live board, and make picks when allowed.
- As a user, I can refresh the draft room without losing the current board state.

### Acceptance Criteria
- Draft lobby shows real league participants, scheduled draft time, and current draft status.
- Draft room reads and writes persisted draft state for the active league.
- Picks are validated against turn order and player availability.
- Refreshing or reopening the draft room restores the current draft board.
- Draft completion populates rosters and exits the league from pre-draft to post-draft status.
- The standalone `/draft` redirect demo path is removed or replaced with a valid league-scoped entry flow.

### Workflow
1. Commissioner schedules or updates the draft from league settings or draft lobby.
2. Members open the draft lobby and see countdown, participant readiness, and draft settings.
3. When the draft starts, clients load the persisted draft board and active pick.
4. Authorized users submit picks for their turn.
5. Draft completion writes final picks, builds roster entries, and updates league state.

### API Specs
- `GET /leagues/:league_id/draft`
  - Response:
    - `draft`
    - `teams`
    - `draft_order`
    - `picks`
    - `current_pick`
    - `status`
- `PATCH /leagues/:league_id/draft`
  - Request body:
    - `draft_datetime_utc`
    - `timezone`
    - `draft_type`
    - `pick_timer_seconds`
- `POST /leagues/:league_id/draft/start`
- `POST /leagues/:league_id/draft/pick`
  - Request body:
    - `team_id`
    - `player_id`
- `POST /leagues/:league_id/draft/pause`
- `POST /leagues/:league_id/draft/resume`
- `POST /leagues/:league_id/draft/complete`

### UI Specs
- Target surface: `web/`
- Draft Lobby must show:
  - league name
  - draft schedule
  - participants
  - commissioner controls
  - join/enter draft action
- Draft Room must show:
  - draft board
  - active pick
  - pick queue
  - team roster preview
  - searchable player list
- Draft state freshness may begin with polling if real-time transport is not yet added.

### Database Specs
- Table: `drafts`
  - Confirm support for:
    - `league_id`
    - `draft_datetime_utc`
    - `timezone`
    - `draft_type`
    - `pick_timer_seconds`
    - `status`
- Table: `draft_picks`
  - Confirm support for persisted order, timestamps, and unique pick sequencing
- If readiness or presence is required, add additive draft-session state rather than overloading picks

### Technical Notes
- Initial implementation may use polling from React instead of websockets if the backend contract remains stable.
- Draft writes must invalidate league workspace and roster caches after completion.

## Rollout Notes
- Phase 1
  - Complete Story 1
  - Finalize React-only route support and docs
- Phase 2
  - Complete Story 2
  - Introduce shared React query hooks and league workspace
- Phase 3
  - Complete Story 3
  - Replace placeholder league hub routes
- Phase 4
  - Complete Story 4
  - Turn roster management and watchlists into persistent workflows
- Phase 5
  - Complete Story 5
  - Remove remaining draft demo behavior

## Testing
- Frontend integration coverage
  - auth bootstrap
  - create league
  - join league
  - league workspace load
  - lineup update
  - add/drop
  - watchlist persistence
  - draft pick submission
- Backend coverage
  - workspace read authorization
  - lineup validation
  - add/drop transaction conflicts
  - watchlist ownership
  - draft turn-order validation
- End-to-end coverage
  - sign up -> create league -> join league -> open league hub -> make roster move -> run draft path
