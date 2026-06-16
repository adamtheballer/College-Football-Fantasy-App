# Architecture Audit

## 1. Executive Summary

The join/create league work was stabilized and committed as `68b5171`. Verification passed across frontend typecheck, frontend tests, frontend build, backend tests, FastAPI health, and Vite HTML smoke.

The codebase is **not ready for unrestricted multiplayer testing** yet. The join/create branch is safe enough to continue from, but the broader product still has server-authority gaps, route-level sprawl, production-dangerous practice draft behavior, frontend state drift, and weak multi-user race coverage.

The most important architectural problem is that too much league/draft behavior lives in oversized route modules and large frontend pages. The most dangerous mechanical problem is that production endpoints can mutate or reset draft/roster data in ways that are not isolated from real league data.

Do not start roster, matchup, or trades feature expansion until the P0/P1 items below are addressed or explicitly accepted as risk.

## 2. Current Git Status

- Current working context: join/create league stabilization work
- Commit created: `68b5171 feat: add join and create league foundation`
- Files committed:
  - `README.md`
  - `api/alembic/versions/0039_unique_real_draft_per_league.py`
  - `api/app/api/routes/leagues.py`
  - `api/app/models/draft.py`
  - `api/app/services/league_flow.py`
  - `tests/api/test_leagues.py`
  - `web/client/components/FloatingQuickActions.tsx`
  - `web/client/components/Layout.tsx`
  - `web/client/pages/DraftHome.tsx`
  - `web/client/pages/LeagueDetail.tsx`
  - `web/client/pages/Leagues.tsx`
- Intentionally uncommitted:
  - `web/client/pages/Index.tsx` contains the unrelated dashboard title fix.
  - `ARCHITECTURE_AUDIT.md` is this audit document and should remain uncommitted until reviewed.
- Excluded from commit:
  - No `.env` files.
  - No API keys.
  - No build output.
  - No debug files.
  - No unrelated dashboard title change.

## 3. Build/Lint/Test Result Summary

- `git diff --check && git diff --cached --check`: passed.
- `npm run typecheck` in `web/`: passed.
- `npm run test` in `web/`: passed, 44 tests across 10 files.
- `npm run build` in `web/`: passed.
- `PYTHONPATH=. uv run pytest -q tests`: passed, 198 tests.
- FastAPI smoke: `curl -fsS http://localhost:8000/health` returned `{"status":"ok"}`.
- Vite smoke: `curl -fsS http://localhost:8080/` returned the app HTML.
- Warnings:
  - Vite build has a large chunk warning for the main app bundle.
  - Backend tests emit Starlette TestClient deprecation warnings for per-request cookies.

## 4. Architecture Overview

- Backend uses FastAPI, SQLAlchemy ORM, Alembic migrations, and service modules under `api/app/services/`.
- Frontend uses React, Vite, TanStack Query, route pages under `web/client/pages/`, reusable components under `web/client/components/`, and API helpers under `web/client/lib/api.ts`.
- Canonical frontend is `web/`; Streamlit `ui/` is not the primary product surface.
- League, draft, roster, trade, and mock draft logic exists, but separation is inconsistent:
  - Real draft APIs are split between `api/app/api/routes/leagues.py` and `api/app/services/draft_service.py`.
  - Mock draft logic is better isolated in `api/app/services/mock_draft_service.py`, but UI routes and shared draft components still create navigation ambiguity.
  - Roster and trade logic exist as separate APIs, but concurrency protections are not consistently server-authoritative.

## 5. Major Structural Problems

- `api/app/api/routes/leagues.py` is a 4,000+ line god module mixing league CRUD, join flow, draft room, admin actions, scoring, notifications, practice setup, queues, and draft picks.
- `api/app/services/draft_service.py` is a 1,000 line service with real draft state serialization, timer behavior, pick submission, roster writes, and conflict handling.
- `api/app/services/mock_draft_service.py` is a 1,300+ line service. It is separate from real drafts, but still too large to safely reason about.
- `web/client/pages/Draft.tsx` is nearly 2,000 lines and mixes board rendering, pick flow, queue behavior, timers, errors, and view state.
- `web/client/pages/CreateLeague.tsx` is almost 900 lines and mixes wizard state, validation, league templates, review UI, and submission.
- `api/app/api/routes/rosters 2.py` appears to be a duplicate or abandoned roster route file. It is not imported by `api/app/main.py`, but its presence is risky and confusing.
- Backend route modules often commit transactions directly while service modules also commit, causing unclear transaction ownership.

## 6. Major Mechanical/Code Problems

- The codebase passes tests, but important behavior is protected by application checks rather than database constraints and transactions.
- Several large route handlers perform multiple writes and commits instead of a single explicit unit of work.
- Frontend state uses `localStorage` for active league selection, which can survive sign-out/sign-in and point at a league the current user should not see.
- `web/client/lib/api.ts` stores access tokens in `localStorage`; this is workable for local development but increases XSS blast radius.
- `CreateLeague` frontend roster defaults do not match backend fixed roster slots.
- Multiple status vocabularies appear in the frontend and backend, including `draft_scheduled`, `draft_live`, `scheduled`, `live`, `paused`, `countdown`, and `lobby_open`.
- Error handling is inconsistent. Some routes return structured conflicts; others rely on raw integrity failures or generic errors.

## 7. Multiplayer Risks

- Join flow is not serialized around league capacity. Two users can pass the same capacity check concurrently because `join_league` counts members before insert without locking the league row or enforcing max capacity at the database level.
- Draft pick submission is much stronger than join flow: it row-locks the draft and uses unique constraints for pick number and player uniqueness.
- Commissioner draft start/status transitions are still risky. Status updates can move drafts into countdown/live-ish states and are not modeled as a strict state machine.
- The frontend mostly relies on polling/query invalidation and current API responses. It has some realtime infrastructure on the backend, but the UI is not uniformly realtime-authoritative.
- Two users on different devices can see stale league/draft state until query refresh or invalidation runs.
- Trade and roster operations are not consistently row-locked against each other, so future simultaneous add/drop/trade behavior is vulnerable.

## 8. Draft Integrity Risks

- Good protections now exist:
  - `drafts.league_id` has unique constraint `uq_drafts_league_id`.
  - `draft_picks` has unique constraints for `(draft_id, overall_pick)`, `(draft_id, player_id)`, and `(draft_id, idempotency_key)`.
  - `roster_entries` has unique constraints for `(team_id, player_id)` and `(league_id, player_id)`.
  - Pick submission locks the draft row before calculating the next pick.
- Remaining risks:
  - Practice setup can delete real `DraftPick`, `RosterEntry`, and bot teams for a league through the real league draft-room route.
  - Starting/resuming/status updates are scattered and not modeled as a single state machine.
  - Real draft can transition from scheduled to live on first pick, which makes draft start implicit rather than an explicit commissioner action.
  - Draft rescheduling creates a draft if one is missing and commits internally. The new unique constraint limits duplication, but the service still lacks a clean transaction boundary.
  - Draft finalization exists in pick submission, but downstream UI unlock/lock behavior is inconsistent.

## 9. Auth/Security Risks

- `POST /players` is unauthenticated and creates player records. That is not safe for any shared server.
- `POST /leagues/join-by-code` now requires authenticated user context, which is correct.
- League member and commissioner helpers exist and are used in many high-risk league routes.
- Audit-log access appears available to ordinary league members. That may be acceptable for transparency, but if it contains admin-sensitive metadata it should be commissioner-only.
- Access tokens are stored in `localStorage`; a frontend XSS bug can steal active sessions.
- Permission checks are mostly server-side for draft picks, league membership, and commissioner actions, but the codebase still has frontend-only UX gates that should not be treated as security.

## 10. Database/Schema Risks

- The draft uniqueness migration is correct and belongs to the branch.
- League member, team ownership, roster player, and draft pick uniqueness constraints are good foundations.
- There is no database-level protection for `League.max_teams`; capacity enforcement is application-only and race-prone.
- `League.invite_code` itself is nullable and not visibly unique on the `leagues` table. Invites may be handled through `LeagueInvite`, but direct use of `league.invite_code` should be audited.
- Trade offer items do not appear to have database uniqueness constraints preventing duplicate player rows inside one offer.
- Several destructive operations rely on route-level authorization and ad hoc checks rather than durable data constraints.
- Cascade behavior should be reviewed before deleting leagues, drafts, teams, and players in shared environments.

## 11. UI/Navigation Risks

- The plus-button quick action now routes mock draft creation separately, which is good.
- The left Draft tab is hidden except for scheduled/live/paused real drafts, which prevents some stale completed-draft entry.
- Roster, matchup, waiver, and trade tabs remain visible even when the league may not be post-draft or user-ready.
- `useActiveLeagueId` persists active league in `localStorage` globally, not per user.
- Join/create flows navigate successfully, but active league and draft status can drift from server state.
- `README.md` and environment examples still reference frontend port `5173`, while the current Vite smoke target is `8080`.
- Mobile responsiveness was not deeply validated in this audit; the large page components are likely to make mobile regressions harder to isolate.

## 12. Testing Gaps

Existing tests cover many important paths, including authenticated join preview, duplicate join rejection, completed-draft join rejection, draft pick conflicts, out-of-turn picks, scheduled draft activation, completion, mock drafts, and trades.

Missing or insufficient tests:

- Creating a league under retry/idempotency conditions.
- Joining a nearly-full league with concurrent users.
- Preventing over-capacity leagues under simultaneous joins.
- Commissioner starting draft twice from two clients.
- Draft status transition matrix.
- Duplicate draft prevention at the migration/database level.
- Full real draft from creation through final roster assignment.
- Real draft practice setup cannot destroy production data.
- Mock draft cannot write to real `draft_picks`, `roster_entries`, or real teams.
- Navigation after draft completion hides/disables draft and unlocks roster/matchup correctly.
- Stale `localStorage` active league after switching users.
- Multi-device browser-level behavior.
- Unauthenticated write endpoints such as `POST /players`.

## 13. Deployment/Testing Readiness

- Multiple people can test locally only if they share the same reachable backend, frontend, and database.
- The current setup is still local-first. It can support shared testing through a tunnel or preview deployment, but environment documentation is not tight enough.
- Recommended shared test options:
  - Vercel preview or equivalent for frontend.
  - Hosted FastAPI backend or tunnel for backend.
  - Cloud Postgres or a single shared database.
  - Explicit `VITE_API_BASE_URL`, `UI_BASE_URL`, `PUBLIC_WEB_URL`, CORS, and cookie settings.
- What would break across devices:
  - `localhost` API defaults in the frontend.
  - CORS/origin mismatch if public URLs are not configured.
  - Local SQLite/local Postgres if not shared.
  - Refresh/session behavior if secure cookie settings are wrong.
  - Stale state without realtime/polling consistency.

## 14. Ranked P0/P1/P2/P3 Issue List

### P0 — App-Breaking / Corrupts League or Draft Data

1. Practice setup can wipe real league draft and roster data.
   - Problem: `practice-setup` deletes real draft picks, roster entries, and bot teams in the real league context.
   - Why it matters: A commissioner can destroy real draft/roster data after a league has meaningful state.
   - Files: `api/app/api/routes/leagues.py:1844`, `api/app/api/routes/leagues.py:1889`, `api/app/api/routes/leagues.py:1890`, `api/app/api/routes/leagues.py:3295`.
   - Risk if ignored: Real leagues can be corrupted or reset.
   - Recommended fix: Remove this from production real league routes or hard-gate it behind development/test mode and empty-draft-only checks.
   - Fix before roster/matchup: yes.
   - Fix before trades: yes.

2. `POST /players` is unauthenticated.
   - Problem: Any caller can create player records.
   - Why it matters: Shared server data can be polluted or manipulated.
   - Files: `api/app/api/routes/players.py:42`, `api/app/main.py:104`.
   - Risk if ignored: Player table corruption and fake player injection.
   - Recommended fix: Require admin/internal auth, move import/upsert to an ops route, or disable in production.
   - Fix before roster/matchup: yes.
   - Fix before trades: yes.

### P1 — Serious Architecture Flaw Blocking Multiplayer

3. League join capacity is race-prone.
   - Problem: `join_league` checks member count before insert without locking or database capacity enforcement.
   - Why it matters: Two users can join at the same time and exceed `max_teams`.
   - Files: `api/app/services/league_flow.py:162`, `api/app/services/league_flow.py:190`, `api/app/models/league.py:16`.
   - Risk if ignored: Overfilled leagues and broken schedules/drafts.
   - Recommended fix: Lock the league row during join, count inside the transaction, and add a concurrency test.
   - Fix before roster/matchup: yes.
   - Fix before trades: yes.

4. League route module is too large to reason about safely.
   - Problem: `leagues.py` mixes unrelated domains across thousands of lines.
   - Why it matters: High-risk changes will continue to couple join, draft, scoring, notifications, and admin behavior.
   - Files: `api/app/api/routes/leagues.py`.
   - Risk if ignored: Regression rate rises as roster/matchup/trade features expand.
   - Recommended fix: Split into league CRUD, joins, draft room, draft picks, league game, admin, and invitations modules.
   - Fix before roster/matchup: yes, at least for touched areas.
   - Fix before trades: yes, at least route boundaries.

5. Transaction ownership is unclear.
   - Problem: Services such as join/reschedule commit internally while routes may also commit related work.
   - Why it matters: Partial updates and rollback behavior become unpredictable.
   - Files: `api/app/services/league_flow.py:198`, `api/app/services/league_flow.py:277`, `api/app/api/routes/leagues.py:4128`.
   - Risk if ignored: Hard-to-reproduce partial state in join/create/draft workflows.
   - Recommended fix: Make routes own commits or use explicit unit-of-work helpers; avoid nested ad hoc commits.
   - Fix before roster/matchup: yes.
   - Fix before trades: yes.

6. Draft status transitions are not a strict state machine.
   - Problem: Status changes are scattered across route handlers and pick submission.
   - Why it matters: Draft start/restart/pause/complete behavior is hard to prove.
   - Files: `api/app/api/routes/leagues.py:3329`, `api/app/services/draft_service.py:653`, `api/app/services/draft_service.py:839`.
   - Risk if ignored: Duplicate starts, invalid resumes, or confusing completed draft behavior.
   - Recommended fix: Centralize status transitions in a draft state machine service with tested allowed transitions.
   - Fix before roster/matchup: yes.
   - Fix before trades: no, unless trades depend on draft completion.

7. Frontend active league is not user-scoped.
   - Problem: `localStorage` stores one active league ID across users.
   - Why it matters: A different user on the same browser can inherit stale or unauthorized league context.
   - Files: `web/client/hooks/use-active-league.ts:3`.
   - Risk if ignored: Wrong league displayed, wrong navigation state, confusing multi-user demos.
   - Recommended fix: Scope active league by authenticated user ID and validate membership on load.
   - Fix before roster/matchup: yes.
   - Fix before trades: yes.

8. Trade and roster mutations lack comprehensive row locking.
   - Problem: Trade accept and roster add/drop/swap rely heavily on checks plus DB constraints, but do not consistently lock roster rows.
   - Why it matters: Simultaneous trade/add/drop operations can conflict unpredictably.
   - Files: `api/app/api/routes/trades.py:185`, `api/app/api/routes/trades.py:641`, `api/app/services/roster_service.py:154`, `api/app/services/roster_service.py:269`.
   - Risk if ignored: Future trade branch can corrupt or reject valid roster state under concurrency.
   - Recommended fix: Lock affected teams/roster rows in one transaction and add race tests.
   - Fix before roster/matchup: yes for roster writes.
   - Fix before trades: yes.

### P2 — Medium Bugs / Bad UX

9. Roster/matchup/trade navigation unlock rules are incomplete.
   - Problem: Tabs are visible even when league state may not support them.
   - Why it matters: Users can enter unfinished or invalid flows.
   - Files: `web/client/components/Layout.tsx:63`, `web/client/App.tsx:226`.
   - Risk if ignored: Broken or confusing UX before draft completion.
   - Recommended fix: Gate tabs by server league workspace state and show disabled explanations.
   - Fix before roster/matchup: yes.
   - Fix before trades: yes.

10. Frontend and backend roster slot defaults disagree.
   - Problem: Frontend review defaults differ from backend fixed slots.
   - Why it matters: Users can confirm a league setup that is not what the backend creates.
   - Files: `web/client/pages/CreateLeague.tsx:150`, `api/app/services/league_flow.py:29`.
   - Risk if ignored: Trust loss and roster-capacity confusion.
   - Recommended fix: Source roster templates from backend or share constants.
   - Fix before roster/matchup: yes.
   - Fix before trades: no.

11. Environment docs/config still point to mixed frontend ports.
   - Problem: Docs and env examples reference `5173`, while the active Vite smoke target is `8080`.
   - Why it matters: Shared testing and onboarding will fail unnecessarily.
   - Files: `README.md:70`, `README.md:84`, `api/app/main.py:50`, `web/.env.example:2`.
   - Risk if ignored: Broken local/tunnel/Vercel setup.
   - Recommended fix: Standardize dev port and update docs/env defaults.
   - Fix before roster/matchup: no.
   - Fix before trades: no.

12. Duplicate roster route file exists.
   - Problem: `rosters 2.py` duplicates or preserves old route logic.
   - Why it matters: Engineers can patch the wrong file.
   - Files: `api/app/api/routes/rosters 2.py`, `api/app/api/routes/rosters.py`, `api/app/main.py:105`.
   - Risk if ignored: Confusing maintenance and accidental import.
   - Recommended fix: Delete after confirming it is unused, in a separate cleanup commit.
   - Fix before roster/matchup: yes.
   - Fix before trades: no.

13. Mock and real draft navigation has overlapping routes.
   - Problem: Mock drafts have both `/draft/mock/:id/room` and `/mock-drafts/:id/room` style routes.
   - Why it matters: It increases route confusion and redirect bugs.
   - Files: `web/client/App.tsx`, `web/client/pages/MockDraftRoom.tsx`.
   - Risk if ignored: Users land in wrong draft experience.
   - Recommended fix: Keep one canonical route and redirect legacy paths deliberately.
   - Fix before roster/matchup: no.
   - Fix before trades: no.

### P3 — Cleanup / Refactor / Nice-To-Have

14. Large frontend bundle warning.
   - Problem: Vite warns that the main chunk is over 500 kB.
   - Why it matters: Slower load and harder route isolation.
   - Files: `web/client/App.tsx`, large route pages under `web/client/pages/`.
   - Risk if ignored: Performance degrades as features grow.
   - Recommended fix: Route-level code splitting after correctness work.
   - Fix before roster/matchup: no.
   - Fix before trades: no.

15. TypeScript quality is uneven.
   - Problem: Some pages use `catch (err: any)` and large local state objects.
   - Why it matters: Error handling and API contracts are less reliable.
   - Files: `web/client/pages/JoinLeague.tsx`, `web/client/pages/CreateLeague.tsx`, `web/client/pages/Draft.tsx`.
   - Risk if ignored: More runtime-only bugs.
   - Recommended fix: Use typed API errors and smaller hooks/components.
   - Fix before roster/matchup: no, except touched files.
   - Fix before trades: no, except touched files.

## 15. Recommended Fix Roadmap

### Before Any New Feature Branch

1. Disable or production-gate real league `practice-setup`.
2. Require admin/internal authorization for `POST /players`.
3. Add a concurrent join test that proves full leagues cannot overfill.
4. Lock league row during join and keep capacity checks inside the transaction.
5. Standardize transaction ownership for league join/create/reschedule.

### Before Roster/Matchup Branch

1. Remove or quarantine `api/app/api/routes/rosters 2.py`.
2. Make roster tab unlock rules server-driven.
3. Align frontend/backend roster slot templates.
4. Add post-draft navigation tests.
5. Add roster mutation locking tests before expanding roster behavior.

### Before Trade Branch

1. Lock affected roster/team rows during trade accept.
2. Add database constraints for trade offer item uniqueness.
3. Add race tests for accept/cancel/add-drop interactions.
4. Make trade availability depend on post-draft league state.

### Before Merge To `main`

1. Fix all P0 issues.
2. Fix P1 join capacity race.
3. Decide whether route/module split is mandatory before merge or immediately after merge.
4. Update docs/env port mismatch.
5. Re-run the full check suite and smoke tests.

## Architecture Verdict

- Ready for multiplayer testing: no, not beyond controlled local/shared smoke testing.
- Real draft safe exactly once per league: closer, but not fully safe while practice setup and loose status transitions exist.
- Join/create branch safe to continue: yes, with the committed scope.
- Merge into `main` now: no.
- Must fix before merging: P0 issues and join capacity race at minimum.
- Next branch: `fix/multiplayer-draft-safety` or `fix/league-join-concurrency`, before roster/matchup/trades.
