# Manual Shared-Backend Smoke Test

Use this checklist before moving beyond internal alpha. Do not mark friends beta ready until these checks pass against one shared backend and one shared database.

## Status

- Current status: not run.
- Required before friends beta: yes.
- Record tester, date, environment URL, API URL, database target, and pass/fail notes before inviting external testers.

## A. Setup

1. Start one shared backend and database.
2. Start the React web app.
3. Open the app from two separate browsers, browser profiles, or devices.
4. Confirm both clients point to the same API base URL.
5. Confirm the backend `CORS_ORIGINS` includes the web origin.
6. Confirm `GET /health` returns success from the shared API.

## B. Auth

1. User A signs up or logs in.
2. User B signs up or logs in.
3. Refresh both clients.
4. Confirm each client remains logged in through `GET /auth/me`.
5. Confirm User A never sees User B's session data, and User B never sees User A's session data.

## C. League Flow

1. User A creates a league.
2. User B joins the league by invite code or invite link.
3. Refresh both clients.
4. Confirm both users see the same league, member count, and team list.
5. Confirm each user has exactly one team.
6. Try joining twice as the same user and confirm no duplicate team is created.
7. Fill the league to `max_teams` if practical and confirm additional joins are rejected cleanly.

## D. Single-Player Mock Draft

1. User A starts a single-player mock draft.
2. Make a user pick.
3. Let CPU picks advance.
4. Confirm drafted players disappear from the mock available-player list.
5. Confirm User B's real league roster and league state do not change.
6. Reset the mock draft.
7. Confirm mock picks are cleared and no real roster entries, real draft picks, real transactions, or real league statuses changed.

## E. Real Draft

1. User A and User B enter the same league draft room.
2. Confirm both clients show the same on-clock team and pick number.
3. Have the correct user make a valid pick.
4. Confirm the other client receives the update without manual refresh, or within the documented polling delay.
5. Confirm the drafted player disappears from the available-player list.
6. Attempt a duplicate player pick and confirm it fails cleanly.
7. Attempt a wrong-user pick and confirm it fails cleanly.
8. Confirm exactly one real draft pick and one real roster entry are created for the valid pick.
9. If the draft is completed, confirm draft and league statuses update correctly and rosters remain visible.

## F. Trades

1. If trade completion is enabled, submit a valid trade proposal.
2. Accept or approve the trade according to league settings.
3. Confirm both rosters update atomically and remain legal.
4. Try accepting a stale trade after manually changing one involved roster, if using a test environment, and confirm it fails without partial roster changes.
5. Confirm the Trade page labels value output as a basic estimate and does not present it as full roster/schedule validation.

## G. Player Search

1. Search by player name.
2. Search by school.
3. Search by position.
4. Confirm a player outside the first default page can be found.
5. Confirm rostered players are excluded when available-only filtering applies.
6. Confirm drafted players are excluded when available-only filtering applies.

## H. Known Out-of-Scope Checks

1. Confirm playoff brackets are not shown as implemented.
2. Confirm playoff seeding locks and playoff advancement are not advertised as working.
3. Confirm scoring, waivers, roster locks, and trades are described according to the current release-readiness note.
4. Confirm any incomplete system is labeled as alpha, MVP, disabled, or out of scope.

## Required Evidence

- API command/log summary.
- Web command/log summary.
- Backend URL.
- Frontend URL.
- Browser/device combinations used.
- Screenshots or notes for create/join, real draft, mock draft, player search, and trade flow.
- Any failures with reproduction steps.
