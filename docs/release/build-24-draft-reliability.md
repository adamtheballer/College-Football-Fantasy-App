# Build 24 — draft authority and confirmation

Based on main `53dc2796`, including the production live-scoring fixes. This
release addresses the three reconciled draft findings and their directly
related expiry, reconnect, queue and completion safeguards from sections 6–7
and Appendix D of the ESPN native UI audit. It preserves the current CFFB
design, player-card/game-log UI, draft order/board and existing workflows.
It does not certify or implement every unrelated recommendation in the
63-page audit, nor introduce its explicitly deferred product features.

## Behavior

- Live Draft buttons fail closed at the exact authoritative deadline, while
  the server remains responsible for timeout picks. The current turn stays
  visible with “Time expired · Auto-pick pending” until confirmed advancement.
- The mock engine rejects manual picks at/after expiry, including between
  rendering ticks; local timeout picks remain isolated from real leagues.
- Draft GET, pick POST and start POST snapshots reconcile monotonically by
  draft version and server time. Canceled old requests cannot rewind the
  board. Replacing a draft resets its baseline; delayed prior-draft responses
  cannot resurrect it. Receipt time stays tied to the accepted snapshot.
- Versioned mutations are never automatically retried. A lost response is
  reconciled against the exact confirmed pick before reporting success.
- Refresh failures retain inspectable confirmed state, show reconnect/retry
  feedback, and disable stale picks. Drafted queue entries are removed; the
  live queue is explicitly a visit-local research list, not auto-pick input.
- Own confirmed picks roll down for 240 ms, remain fully visible for 2,000 ms,
  then retract for 240 ms. Distinct adjacent picks queue in order. Initial
  history, duplicate snapshots and remounts do not replay old acknowledgements.
  Reduced Motion removes sliding, not the two-second acknowledgement.
- The next clock and roster update independently. Final clocks clear
  immediately; completion waits for queued acknowledgements. Completion uses
  the accessible dialog primitive, Escape dismissal and focus return. Explicit
  final roster/exit controls refetch league state and retain a recoverable
  error if loading fails. Completion also initiates cache refresh immediately.
- Exhausted mock pools report actual pick counts and an incomplete explanation.
- Nested row keyboard handlers no longer intercept Draft/Queue button actions.

## Verification

- TypeScript app, test and Vite configuration checks.
- Full frontend unit/component suite: 445 passing tests.
- Browser fixtures cover zero expiry, accepted/rejected picks, reconnect,
  confirmed-pick timing/deduplication, final timer clearing, dialog focus and
  Escape. Existing draft/mobile/mock regressions also run before release.
- Both website and native production bundles compile. Native API origin stays
  `https://api.collegefantasyfootball.org`; bundle ID and marketing version are
  unchanged; Apple build number is 24.

These are local automated/browser checks, not physical iPhone certification.
Physical-device VoiceOver, background suspension, safe-area extremes and
native Back behavior remain release-device verification items. No real
manager's draft, roster or pick was modified for testing.
