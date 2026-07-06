# Single-Player Mock Draft Manual Test

Run these checks before merging the single-player mock draft cleanup branch.

## Setup

1. Start the backend API and database.
2. Start the React app.
3. Sign in with a test account.
4. Open `/draft`.
5. Click `Start Single-Player Mock`.

## Required Checks

1. The page title says `Single-Player Mock Draft`.
2. No multiplayer mock draft create/join controls are present.
3. The draft starts in an intermission/pre-draft state.
4. Bot pick #1 happens about two seconds after the draft goes live.
5. The draft advances to pick #2 and the timer resets.
6. Bot picks continue until the user team is on the clock.
7. The user can draft only when `Your Turn` says `Draft Now`.
8. If the user timer expires, the app auto-picks from the queue first, then best available.
9. Drafted players disappear from available players.
10. The search box filters player names and schools.
11. Position filters show only the selected position.
12. Filtered players keep their exact pre-draft board `RK` value.
13. RB, WR, and TE projected points do not increase as same-position board rank gets worse.
14. Tight ends after the top five are visible before the late-200s range.
15. Bench cards use the drafted player's position color.
16. Reset clears picks and starts a fresh local mock draft.
17. The draft completes at 156 picks with no duplicate players.

## Data Safety Checks

Single-player mock draft is frontend-local in this branch. It must not call real draft mutation APIs.

Confirm in the browser network panel:

- No `POST /leagues/{league_id}/draft-picks`.
- No `POST /rosters`.
- No league status mutation.
- No real `DraftPick` or `RosterEntry` writes.

## Current Automated Coverage

- `web/client/lib/singlePlayerMockDraft.spec.ts` verifies intermission start, bot pick advance, user-turn enforcement, full 156-pick completion, and duplicate-player prevention.
- `web/client/lib/draftRankings.spec.ts` verifies RB/WR/TE projection monotonicity and TE visibility before the late-200s range.
