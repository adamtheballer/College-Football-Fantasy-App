# Feature 18: Mock Draft Lobby Multiplayer

## Summary
- Replace the current draft sandbox entrypoint with a dedicated mock draft flow under `/mock-drafts`.
- Keep mock draft state isolated from permanent league state.
- Allow multiple authenticated users to join the same mock draft by invite code, ready up, start the room, and complete a live snake draft.

## Backend scope
- Add isolated mock draft tables for sessions, seats, picks, rosters, lobby presence, timers, queues, and events.
- Expose mock draft APIs for create, preview by invite code, join, lobby presence, status transitions, room state, picks, queues, realtime snapshots, websocket subscriptions, and deletion.
- Reuse the existing roster-fit and slot-assignment logic so manual picks and autopicks follow the same legality rules as the main draft room.
- Ensure mock draft operations do not create or mutate league, team, roster, league invite, or league event rows.
- Add stale mock draft cleanup for completed or abandoned sessions older than 24 hours.

## Frontend scope
- Make `/draft` the mock draft entry page.
- Add separate mock draft lobby and room routes.
- Support lobby creation, invite code sharing, join by code, ready toggles, commissioner start/delete actions, and room entry.
- Show only draftable positions for the active seat as enabled draft buttons; invalid positions remain visible but disabled with an explanation.
- Provide a working queue UI for the active user seat.

## Acceptance criteria
- Mock drafts are isolated from permanent league data.
- Multiple users can join the same mock draft by invite code.
- Countdown start requires joined human users to be ready.
- Unclaimed seats become CPU seats when the commissioner starts the mock draft.
- Manual picks and autopicks respect roster legality and never overflow mock rosters.
- Queue endpoints work per mock draft seat.
- Deleting a mock draft removes its mock-only state.

## Tracking
- This requirements file is the repo source of truth.
- Matching GitHub issue creation is still required for project tracking.
