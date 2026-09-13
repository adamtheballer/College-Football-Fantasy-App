# Epic: Native Audit Remediation

## Summary

Implement the actionable Phase A-C findings in the CFFB ESPN Fantasy native-app audit. `web/` React remains the canonical product surface. The work improves reliable state, accessibility, retained mobile context, recovery behavior, and the existing CFFB visual system without copying ESPN assets, data, branding, or unsupported product features.

## In Scope

| Phase | Findings | Outcome |
| --- | --- | --- |
| A - trustworthy state and actions | F01-F06, F21-F23 | Expiry, conflict, reconnect, modal, onboarding, probability, and completion states are truthful and recoverable. |
| B - retained mobile context | F07-F11, F14, F17, F24-F25 | Draft, matchup, carousel, and player research preserve context and use deliberate gestures and motion. |
| C - consistent card and recovery UI | F12-F13, F15-F16, F18-F19 | Player images, loading/empty/error states, labels, recovery copy, and native-size validation are consistent. |

The audit's 41 release checks are the verification matrix for this epic. Each finding is tracked by its audit ID in implementation tests or a release checklist. Device-only checks remain required before an iOS submission.

## Out of Scope

- F20: media, achievements, score drawer, personalized recommendations, and other new product surfaces.
- Replacing the FastAPI draft authority, React, Vite, Tailwind, Radix, or existing player/scoring data contracts.
- Inventing sports data, team artwork, sponsorships, or licensed ESPN assets.
- Claiming physical-device, VoiceOver, background-suspension, large-text, or safe-area certification without executing those checks on supported devices.

## User Stories

- As a manager, I can trust a draft button, timer, confirmation, completion, and reconnect state to reflect authoritative draft data.
- As a manager, I can inspect a player, close the card, and continue my original research task without losing focus, filters, or scroll position.
- As a manager, I can compare matchups while scrolling lineups and move between matchups intentionally on mobile.
- As a manager, I can understand unavailable probabilities, loading, errors, and player availability without developer terminology.

## Acceptance Criteria

### Phase A

- F01/F21-F23: all manual pick paths fail closed at an expired or stale deadline; rejected deterministic picks are not retried; stale snapshots cannot replace newer draft state; a prior confirmed room remains visible during reconnect.
- F02/F06: player and completion dialogs trap focus, have an initial focus target, support Escape, and restore focus to the opener; all completed-draft exits use the same refreshed league/roster resolution.
- F03: keyboard activation of Draft, Queue, Watch, Add, and Claim actions performs only that action and does not also open a player card.
- F04: onboarding does not mutate persistent tab stops or focus background navigation controls; Reduced Motion avoids forced smooth scrolling.
- F05: missing, invalid, or delayed probabilities state that they are unavailable; valid zero and 100 percentages remain visible.

### Phase B

- F07: a confirmed own pick animates into a reserved draft header region, remains for two seconds, retracts, and does not delay the next authoritative clock or replay after reconnect.
- F08/F09: matchup week, teams, totals, status, and honest probability remain available in a compact retained summary while the lineup scrolls; mobile has named previous/next controls and only deliberate horizontal swipes page matchups.
- F10/F11/F14: active parent/league routes are announced correctly; logical carousel items are reachable once; returning to waiver/player research restores its filters and scroll position rather than resetting it.
- F17/F24/F25: explicit JS scrolling honors Reduced Motion; mock exhaustion reports actual committed picks; live and mock queue surfaces state unavailable/drafted reason and do not imply unavailable server auto-pick behavior.

### Phase C

- F12/F13: roster loading is distinct from a confirmed empty roster; trade and waiver loading, errors, empty results, Retry, and Clear filters are mutually coherent.
- F15/F16: player image failures use a stable fallback; all controls have labels and selected state semantics; badges name what they count.
- F18/F19: data limits are measured before pagination changes; mobile/safe-area validation is recorded; manager-facing errors never instruct users to start APIs or mention internal master-board/data-service terms.
- Player cards and game logs use the supplied layout principles: one consistent accessible sheet, direct tab content, readable zebra table rows, semantic tabs, stable image fallback, and no nested decorative game-log card.

## Implementation Workflow

1. Preserve authoritative API data, draft versioning, player IDs, and existing routes.
2. Implement shared accessibility and state primitives before page-local visual changes.
3. Add focused unit/browser coverage for every audit finding before marking it complete.
4. Run release checks against test leagues and controlled browser fixtures; never mutate a real manager's roster to validate UI.
5. Build the iOS artifact only after the audit checklist and a separate physical-device pass are complete.

## API and Database Impact

No schema migration is required for the known UI findings. Existing versioned draft-room, player-card, roster, waiver, and matchup responses remain the source of truth. If audit work exposes a missing endpoint or persistence requirement, it must receive a separate feature contract and migration review before implementation.

## UI Requirements

- Preserve the CFFB dark collegiate system: navy/charcoal surfaces, blue action emphasis, restrained gold, readable off-white data, and semantic availability colors.
- Use shared Radix dialog semantics for temporary layers; do not add custom focus traps per entry point.
- Retained controls must fit the existing shell and safe-area strategy, not use fixed screenshot pixel values.
- Motion supports hierarchy, honors Reduced Motion, and never masks data freshness or authority.

## Release Checks

| Audit checks | Required evidence |
| --- | --- |
| Q01-Q10 | Draft fixtures plus a controlled test league/device session. |
| Q11-Q17 | Browser keyboard and sheet/scroll tests. |
| Q18-Q26 | Mobile matchup/carousel/browser tests and device validation. |
| Q27-Q35 | Deep-link, keyboard, safe-area, text-size, reduced-motion, and offline/device checks. |
| Q36-Q41 | End-to-end draft, conflict, ordering, poll-failure, exhaustion, and queue-contract tests. |

### Explicit release-check register

`Pending device` means the implementation may have focused source coverage but must not be called release-verified until it is exercised on a named test league and review build. No real manager roster may be used for these cases.

| Check | Implementation evidence | Release status |
| --- | --- | --- |
| Q01 Clock | Versioned draft reconciliation and draft-room tests | Pending device |
| Q02 Zero | Expiry guards and disabled pick state | Pending device |
| Q03 Late tap | Server conflict/validation handling | Pending device |
| Q04 Mock expiry | Mock expiry state helpers | Pending device |
| Q05 Banner | `PickConfirmationStrip.spec.tsx` | Pending device |
| Q06 Duplicate | Pick-confirmation dedupe tests | Pending device |
| Q07 Reconnect | Versioned snapshot reconciliation | Pending device |
| Q08 Adjacent picks | Pick-confirmation sequencing tests | Pending device |
| Q09 Final pick | Draft completion dialog flow | Pending device |
| Q10 Exit paths | Draft completion exit routing | Pending device |
| Q11 Draft scroll | Draft-room independent scroll owners | Pending device |
| Q12 Board | Board recenter control | Pending device |
| Q13 Search | Waiver state persistence and player-card close behavior | Pending device |
| Q14 Inner actions | Isolated action event handlers | Pending device |
| Q15 Sheet | Player-card focus and semantic-tab test | Pending device |
| Q16 Modal scroll | Player-card scroll owner | Pending device |
| Q17 Tour | Reduced-motion onboarding behavior | Pending device |
| Q18 Matchup pin | Sticky compact scoreboard | Pending device |
| Q19 Matchup swipe | Axis-aware swipe logic and named controls | Pending device |
| Q20 Probability | Honest unavailable state and 0/100 support | Pending device |
| Q21 Freshness | Existing freshness-state contract | Pending device |
| Q22 Roster load | `LeagueRoster.spec.ts` loading/empty separation | Pending device |
| Q23 Error | Waiver and draft Retry states | Pending device |
| Q24 Portrait | Player-card and carousel fallback tests | Pending device |
| Q25 Names | Responsive truncation and action layout | Pending device |
| Q26 Carousel | `LeagueMatchupCarousel.spec.tsx` clone/control coverage | Pending device |
| Q27 Deep links | Parent-route active-state mapping | Pending device |
| Q28 Keyboard | Shell and input-heavy route check | Pending device |
| Q29 Safe areas | Shared app-shell and modal safe-area styles | Pending device |
| Q30 Text size | Responsive label/number layout | Pending device |
| Q31 Reduce Motion | Global media query and onboarding/banner behavior | Pending device |
| Q32 Slow/offline | Recoverable ErrorState/Retry flows | Pending device |
| Q33 Native back | Modal focus restoration and retained scroll | Pending device |
| Q34 Counts | Explicit navigation badge labels | Pending device |
| Q35 Background event | Banner reconnect suppression | Pending device |
| Q36 Full session | Test-league draft/lineup flow | Pending device |
| Q37 Rejected pick | Conflict reconciliation tests | Pending device |
| Q38 Response order | Stale snapshot ordering tests | Pending device |
| Q39 Poll failure | Last confirmed snapshot recovery | Pending device |
| Q40 Mock pool exhausted | Mock exhaustion helper tests | Pending device |
| Q41 Queue contract | Live/mock queue unavailable-state contract | Pending device |

## Rollout Notes

- Build 24 is an interim draft reliability artifact, not the completion of this epic.
- Do not upload a replacement Apple build until the selected audit scope and physical-device matrix have passed.
