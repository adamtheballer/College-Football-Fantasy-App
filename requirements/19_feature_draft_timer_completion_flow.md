# Feature 19: Draft Timer Completion Flow

## Summary
Fix live/single-player draft timer authority so a 12-manager, 13-round draft advances through all 156 picks, completes cleanly, and presents a draft-history email/exit flow.

## Stories

### Story 1: Authoritative Draft Math
- As a drafter, I need draft round/pick math to stay correct through late rounds so Round 9 Pick 10 maps to overall pick 106 and the draft never stalls from derived index errors.
- Acceptance: pure draft engine tests cover 156 total picks, snake reversal, Round 9 Pick 10, and final-pick completion.

### Story 2: Persisted Pick Timer
- As a drafter, I need each pick to have persisted start and expiry timestamps so the UI can recover from polling, reconnects, and late-round transitions without freezing.
- Acceptance: manual and auto picks reset `current_pick_started_at` and `current_pick_expires_at`; completed drafts clear expiry.

### Story 3: Auto-Pick Continuity
- As a single-player/mock drafter, I need expired picks to auto-select the best legal available player so CPU/user timeout turns continue through pick 156.
- Acceptance: explicit auto-pick endpoint validates live state, timer expiry or test force, roster fit, drafted/rostered exclusions, and returns updated room state.

### Story 4: Completion and History
- As a drafter, I need a completed draft to show history email options and let me exit back to the general draft tab.
- Acceptance: completed rooms expose exit/email flags; history endpoints produce plain text/HTML; modal allows send, skip, copy, and exit.
