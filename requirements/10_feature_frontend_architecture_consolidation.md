# Feature: Frontend Architecture Consolidation

## Description
Converge the product onto a single supported frontend architecture so league creation, join, roster, matchup, and settings workflows all use the same auth model, route model, and backend contracts.

## In Scope
- Declare `web/` React as the primary supported product surface
- Remove `ui/` Streamlit app code, local dev flow, and product references from the repo
- Replace mock-driven league workspace flows in React with backend-backed data
- Introduce a shared auth bootstrap and typed query layer in React
- Standardize route identity and remove demo slug fallback behavior
- Gate unfinished routes so the main router only exposes supported flows

## Out of Scope
- Visual redesign of existing React pages
- New fantasy features beyond stabilizing current core workflows

## User Stories
- As a signed-in user, I can trust that the league pages show my real leagues, teams, rosters, and settings.
- As a signed-in user, I stay authenticated across supported React routes without each page reimplementing auth state.
- As a product team, we can point to one supported UI surface for core workflows and one set of contracts for backend integration.

## Acceptance Criteria
- `web/` is the only supported product surface for core league workflows in README, routing, and implementation notes.
- Streamlit app code and Streamlit-specific product flows are removed from the repo.
- Streamlit-specific local development, dependency, and environment references are removed or replaced.
- React league pages do not rely on hardcoded mock roster, matchup, standings, or trade data for supported flows.
- React auth is bootstrapped once at app load and protected routes redirect unauthenticated users consistently.
- Core league data access is implemented through shared typed hooks or query helpers rather than page-local fetch orchestration.
- Route identity is consistent for league pages.
  - Supported league routes use numeric internal IDs.
  - Demo slug fallbacks such as `saturday-league` are removed from supported flows.
- Unfinished pages registered in the main router are either feature-flagged, marked demo-only, or removed from the supported navigation.

## Workflow
1. Mark `web/` as the supported frontend in repo docs and implementation planning.
2. Add an app-level session bootstrap that loads stored auth, validates session state, and exposes protected route helpers.
3. Add a React data layer with typed hooks for auth, leagues, league workspace, notifications, and settings.
4. Replace mock-driven league home, roster, matchup, and trade hydration with backend-backed contracts.
5. Remove demo slug routing and standardize links, redirects, and deep links on numeric league IDs.
6. Gate or remove incomplete routes from the primary router until they are backed by real contracts.
7. Remove the Streamlit app tree and clean up repo references, local scripts, and dependencies that exist only for Streamlit.

## API Specs
- Existing endpoints to keep and support through React
  - `POST /auth/signup`
  - `POST /auth/login`
  - `GET /leagues`
  - `GET /leagues/:league_id`
  - `POST /leagues`
  - `POST /leagues/:league_id/join`
  - `PATCH /leagues/:league_id/settings`
  - `PATCH /leagues/:league_id/draft`
  - `GET /notifications/preferences`
  - `POST /notifications/preferences`
  - `GET /notifications/league-preferences`
  - `POST /notifications/league-preferences`
- New or revised contract needed for the React league hub
  - `GET /leagues/:league_id/workspace`
  - Response includes:
    - league detail
    - current user membership
    - current user team
    - roster with player detail
    - matchup summary for the selected week
    - standings preview
    - allowed actions for the current user
- Contract cleanup
  - Canonical league creation route should be `POST /leagues`
  - `POST /leagues/create` should be treated as temporary compatibility only and removed after migration

## UI Specs
- App shell
  - Add a single auth/session provider near the app root
  - Add protected route behavior for create league, join league, league detail, roster, alerts, and settings
- Data layer
  - Add typed hooks such as `useSession`, `useLeagues`, `useLeagueWorkspace`, `useNotificationPreferences`
  - Use shared loading, empty, and error states instead of page-specific silent fallbacks
- League list
  - Stop loading list IDs and then N+1 fetching details
  - Render from a single list contract or a query hook that handles detail hydration centrally
- League detail
  - Remove `allPlayersMock` and league mock seed fallback from supported flows
  - Hydrate roster, matchup, standings, and invite state from backend contracts
  - If data is unavailable, show an explicit unsupported or empty state instead of synthetic league content
- Router cleanup
  - Remove redirect from `/draft` to a demo slug
  - Remove placeholder pages from the supported route tree unless they are explicitly feature-flagged
- Repo cleanup
  - Remove Streamlit routes, pages, auth helpers, components, themes, mock generators, and legacy views under `ui/`
  - Update README and local run instructions to use the React app only
  - Remove Streamlit-specific env vars and dependency references where they are no longer needed

## Database Specs
- No schema change required solely for the React data layer
- Backend support for `league workspace` may require additive query support and indexes handled in the backend story

## Technical Notes
- Recommended implementation path
  - Keep `web/` as the production UI
  - Remove `ui/` entirely rather than carrying a second unsupported product surface
- React implementation details
  - Replace page-local `useEffect` fetch blocks with TanStack Query hooks and shared cache keys
  - Add a `ProtectedRoute` wrapper or equivalent route guard
  - Add a session bootstrap call or local token validation pass before rendering authenticated screens
  - Normalize transport errors into user-readable states rather than falling back to empty arrays or mock data
- Streamlit removal details
  - Remove `streamlit` from `pyproject.toml` dependencies
  - Remove Streamlit startup from `scripts/dev.sh`
  - Update `README.md` to document React plus API as the only local UI flow
  - Remove `UI_API_BASE_URL` from `.env.example` if no longer required elsewhere
- File targets
  - `web/client/App.tsx`
  - `web/client/hooks/use-auth.ts`
  - `web/client/lib/api.ts`
  - `web/client/pages/Leagues.tsx`
  - `web/client/pages/LeagueDetail.tsx`
  - `web/client/pages/Rosters.tsx`
  - `web/client/pages/Trade.tsx`
  - `web/client/pages/Settings.tsx`
  - `README.md`
  - `pyproject.toml`
  - `scripts/dev.sh`
  - `.env.example`
  - `ui/`

## Rollout Notes
- Phase 1
  - Mark React as primary
  - Add auth bootstrap and route guards
  - Remove demo route redirects from supported navigation
  - Remove Streamlit from docs and local dev startup
- Phase 2
  - Introduce typed query hooks
  - Replace league detail and roster mock hydration
- Phase 3
  - Move remaining supported pages off mock data
  - Delete the remaining Streamlit code and dependency surface
- Testing
  - Add frontend integration coverage for login, league list, create league, join league, and league detail
  - Add one end-to-end path that validates the React app against the canonical backend contracts
