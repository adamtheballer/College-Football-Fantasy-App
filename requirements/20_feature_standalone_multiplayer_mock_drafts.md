# Feature 20: Standalone Multiplayer Mock Drafts

## Summary
Build account-required, standalone multiplayer mock drafts that are completely separate from real league drafts. Mock drafts use invite codes, scheduled starts, pre-draft intermission, randomized draft order, humans plus bots, server-owned timers, auto-picks, completion history email prompts, retention cleanup, and exit back to `/draft`.

## Non-Negotiable Boundaries
- Mock drafts are practice drafts only and never affect real leagues.
- Mock draft actions must never write `Draft`, `DraftPick`, `RosterEntry`, `League.status`, `LeagueInvite`, or real team roster state.
- Mock drafts may read authenticated users, player/ranking/projection data, and email configuration.
- Mock draft writes are limited to mock draft session, participant, pick, event, and history/email/retention records.

## Stories

### Story 1: Draft Home and Creation
- As an authenticated user, I can open `/draft`, create a scheduled standalone multiplayer mock draft, and receive a copyable invite code/link.
- Acceptance: `/draft` is a real draft hub; creation requires auth; settings validate team count, rounds, timer, future start time, player pool, scoring, and bot difficulty.

### Story 2: Account-Required Invite Joining
- As an authenticated invitee, I can join by invite code before the draft locks, while guests and late joiners are rejected.
- Acceptance: invite codes are unique, uppercase, case-insensitive, non-predictable, and joining fails for invalid, full, cancelled, completed, expired, intermission, or live drafts.

### Story 3: Scheduled Lock and Intermission
- As participants, we cannot start early; the backend locks settings at the scheduled time, fills empty seats with bots, randomizes draft order once, and opens a 30-second intermission.
- Acceptance: draft order is persisted, humans and bots are both participants, no frontend randomization occurs, and refreshes deterministically advance scheduled/intermission/live state.

### Story 4: Server-Owned Mock Draft Room
- As a participant, I can enter the room and see the current round/pick, on-clock participant, timer, available players, picks, rosters derived from mock picks, and completion state.
- Acceptance: room access requires existing participation, server time and expiry are authoritative, timer resets every pick, and frontend polling only displays backend state.

### Story 5: Human and Auto Picks
- As a drafter, I can pick only on my turn; bots and expired human timers auto-pick safely without duplicate picks or skipped overall pick numbers.
- Acceptance: picks write only `MockDraftPick`, use transactions/idempotency, reject duplicate players, handle duplicate auto-pick calls, and never create real roster entries.

### Story 6: Completion, History, Email, and Exit
- As a participant after completion, I see a one-time email-history prompt, can send or skip, can copy/download fallback history, and can exit back to `/draft`.
- Acceptance: final pick completes the draft, history includes all picks grouped by round and team, email failure returns 503 fallback content, emailing preserves history longer, and skipping leaves it eligible for cleanup.

### Story 7: Retention Cleanup
- As the system, I can remove expired unsaved mock drafts without deleting preserved emailed histories prematurely.
- Acceptance: unsent completed mock drafts expire after 24 hours, emailed histories preserve for 30 days, and cleanup deletes only expired unpreserved/cancelled/expired mock data.

### Story 8: Regression Safety
- As maintainers, we can prove mock drafts do not contaminate real draft state and can complete a 12-team, 13-round simulation.
- Acceptance: backend tests cover creation, joining, scheduled transitions, order lock, snake math, human/bot/timer picks, 156-pick completion, email fallback/success, cleanup, and no real table writes; frontend tests cover hub, forms, lobby, timers, auto-pick triggers, completion modal, email, and exit.
