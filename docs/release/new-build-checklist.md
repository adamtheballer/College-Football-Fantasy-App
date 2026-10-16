# Combined New Build — held locally

Workspace: `College-Football-Fantasy-App-recovered`, existing branch
`codex/full-height-sidebar-player-colors`. Preserve prior sidebar/player-card
changes. No task in this combined release authorizes a push, merge, deployment,
production migration, archive/upload, TestFlight or App Store release. Release
only after the remaining list is complete and the owner explicitly authorizes it.

## Item 1 — automatic native iOS App Review

**Implemented and tested, including actual native simulator invocation.**
Apple-controlled dialog display/submission and physical-iPhone verification remain
separate checks; the initial UI automation interruption was superseded by the
passing native XCTest host flow recorded below.

Architecture: React/Vite in Capacitor 8, Swift target iOS 15+, FastAPI/JWT,
immutable `users.id`, existing Keychain refresh/session restoration. Layout owns
the single invisible coordinator. Existing verification policy is disabled;
review endpoints use the existing verified-user dependency and cannot bypass a
future required-verification policy. Existing onboarding is respected. No prior
automatic review trigger or voluntary Rate CFFB link was found.

Files: `api/app/{api/routes,schemas,services}/app_review.py`, `models/user.py`,
`core/config.py`, public runtime schema/inspector, `main.py`, migration 0117;
`web/client/lib/{app-review,native-app-review,review-presentation}.ts`, coordinator
component/Layout, API/runtime capability utilities, native notification blocker;
Swift `AppReviewPlugin.swift`, `AppReviewPolicy.swift`, SceneDelegate and project
source registration. Tests and local Bruno requests accompany the implementation.

The backend performs a single `UPDATE users ... WHERE id = verified_account AND
review_request_claimed_at IS NULL RETURNING ...`, and commits before granting.
PostgreSQL serializes competing devices and rechecks the condition. Account
preconditions prevent switched/refreshed auth consuming a different account.
The ledger stores only timestamp/version/build and has a metadata constraint.
There is no review-completed flag, display guarantee, rewards or custom pre-prompt.

The coordinator waits three unobstructed seconds, checks native availability and
authenticated state, atomically claims, caches consumption before invocation,
rechecks the release switch/session/native scene, and invokes at most once.
Account change, logout, background, modal, onboarding, loading, forms, user
interaction or conflicting routes cancel pending work. Browser visits never call
review endpoints. Native uses `AppStore.requestReview(in:)` on iOS 16+ and
`SKStoreReviewController.requestReview(in:)` on iOS 15, on the bridge's actual
active scene with independent account/context/consumption guards.

Native Settings verification exposed and fixed an overly broad window guard:
UIKit retained a visible non-key `UITextEffectsWindow` at normal + 1 after editing
ended. Treating every elevated window as a modal blocked review on an otherwise
safe Home screen. The plugin now explicitly tracks keyboard show/hide, checks the
active key scene and presented controllers, and blocks alert-level windows.
The actual simulator flow confirms invocation after editing with the text-effects
window still present; no private UIKit APIs or window class-name filtering are used.

A lost response or crash after commit may consume eligibility without a dialog.
Uncertain claims are reconciled by reading state, never replaying a grant in that
visit. Network work is bounded to two opportunities per account/mount, separated
by 30 seconds and a later safety/lifecycle event; no repeated polling. Server
state survives reinstall/update/devices/name/email changes. Local caches add
protection but cannot authorize a request.

`IOS_APP_REVIEW_ENABLED=false` is the default/example. Disabling cancels local
pending work; state/claim/final confirmation enforce the backend switch. A running
session with stale runtime configuration still fails closed at the server. An
enabled-to-disabled rollout must update every API replica. Re-enabling never
clears the ledger. New enabled sessions receive the capability at startup.

Validation: 36 deterministic coordinator tests, 20 Layout/DOM integration tests,
17 PostgreSQL API tests including simultaneous devices, 12 Swift policy assertions,
and Debug simulator-target compile. Migration certification exercised full history,
NULL backfill for existing accounts, constraints, downgrade/re-upgrade, refusal to
drop a consumed ledger, column parity and `alembic check` (no operations detected).
Authentication regression tests passed; current combined counts are recorded below.

Apple controls display and submission; TestFlight requests have no effect.
References: [requesting reviews](https://developer.apple.com/documentation/storekit/requesting-app-store-reviews),
[review guidelines](https://developer.apple.com/app-store/review/guidelines/#app-store-reviews).

## Item 2 — account/display name in Settings

**Implemented and tested in backend, frontend, real browser and native simulator.**
Remaining physical-device and production checks are recorded below.

Confirmed reproduction on isolated data: a name last changed 192 hours ago fails
with HTTP 422 when the old Settings payload resends an unchanged invalid legacy
avatar; the identical name-only request returns 200 and persists. This proves
payload coupling, not a seven-day rejection. Device-time comparisons and cached
eligibility in the old Settings implementation can also lock an eligible user;
old error feedback gave only a date. No production account was inspected, so
the reported individual's specific stored state remains unconfirmed.

The old backend correctly allowed an expired single-request cooldown, but read
the auth dependency's cached user and updated without a row lock: simultaneous
devices could both pass. Its Retry-After truncated fractional seconds. The old
AuthProvider also accepted late profile responses without an account/sequence
guard and awaited cache refetches before reporting an already-persisted save.

Files: `api/app/core/name_change.py`, `services/profile_names.py`,
`schemas/name_change.py`, `api/routes/auth.py`, `models/user.py`;
`web/client/lib/name-change.ts`, `hooks/use-name-change-eligibility.ts`,
Settings, AuthProvider and API utilities; backend/frontend regression tests,
local Bruno requests, isolated E2E account seeder and real-stack browser tests.

One canonical deadline is the dedicated successful-change UTC timestamp +168
elapsed hours. Server time >= deadline qualifies exactly at expiration. PostgreSQL
locks/reloads the user, obtains `clock_timestamp()` after acquiring the lock, checks
eligibility and commits name/timestamp/team-owner synchronization together. An
unchanged name is a no-op; avatar/login/review metadata and failed submissions do
not advance this timestamp. Existing validation, first-change-free policy, custom
team labels and verified account ownership are preserved.

GET `/auth/me/name-change-eligibility` returns account/current name and timing.
PATCH `/auth/me` returns the committed profile. Example one-second rejection:

```json
{
  "detail": {
    "code": "NAME_CHANGE_COOLDOWN",
    "field": "first_name",
    "message": "Your manager name is still in its seven-day change window. Unsuccessful attempts do not restart the wait.",
    "account_id": 7,
    "current_name": "Manager",
    "server_time": "2026-10-13T12:00:00Z",
    "last_successful_change_at": "2026-10-06T12:00:01Z",
    "next_eligible_at": "2026-10-13T12:00:01Z",
    "retry_at": "2026-10-13T12:00:01+00:00",
    "remaining_wait_seconds": 1,
    "can_change_name": false
  }
}
```

`Retry-After: 1`. Remaining seconds use ceiling and never return zero while
rejecting. Validation/auth/permission/network/storage failures do not become
cooldown errors. Settings sends changed fields, guards duplicate taps, confirms
the persisted response, updates account caches and invalidates league/chat views.
Account/sequence/abort guards reject stale responses. Availability refreshes on
open, foreground, success/rejection and estimated expiration. Countdown uses
`performance.now()` relative to server timing; expiration is re-confirmed by the
server. Failure shows Retry, not a fabricated seven-day lock. Inline wait includes
days/hours/minutes, less-than-a-minute text and the exact localized deadline.

No item-2 migration or data repair is staged: migration 0106 added a nullable
dedicated timestamp without a backfill, signup leaves it NULL, and inspected
writers advance it only on successful name changes. No evidence supports a mass
reset or invented historical correction. If a specific production record later
proves corrupted, investigate and stage a narrowly evidenced repair separately.

## Item 3 — remove outdated Week 1 Pick 6 from Home

**Removed and verified on guest and authenticated Home, desktop/mobile and native.**
The promotion was mounted unconditionally rather than being gated by its event
date. Removed the entire Home promotion component and both contest links, replaced
the guest feature tile with Waivers, and removed stale Coming Soon claims that
advertised Pick 6 on Home. Existing league, roster, draft, standings and alerts
sections remain functional. The dedicated contest route and backend were outside
the requested Home removal scope and are unchanged.

Files: `web/client/pages/{Index.tsx,Index.spec.tsx,ComingSoon.tsx}` and
`web/tests/e2e/home-without-pick6.spec.ts`. The native host test also checks Home
contains neither the promotion nor its contest links.

## Verification ledger

- Backend SQLite/default suite: **106 passed**, two PostgreSQL-only tests skipped.
- PostgreSQL suite for both features: **37 passed**, including both concurrency tests.
- Full frontend unit/component suite: **561 passed in 89 files**, including the
  fractional-second expiration regression and prior sidebar/player-card tests.
- TypeScript app/test/Vite checks and web production build: **passed**.
- Swift policy assertions: **12 passed**. Debug simulator-target compile: **passed**.
- Real Chromium with the actual isolated FastAPI/PostgreSQL stack: **2 passed**.
  An account changed 192 hours earlier with an unchanged invalid legacy avatar
  saves a name-only PATCH, reports the new cooldown, and survives reload. A page
  left open unlocks at server expiration with device time set to 2000, then saves.
  Browser visits made no App Review calls even with the local review switch on.
- Home removal with that real stack: **4 passed**, covering guests and signed-in
  users at 1280px and 390px. No Pick 6 text, links, contest network requests or
  browser review requests remain on Home; league navigation works and neither
  viewport overflows. Desktop/mobile screenshots were visually inspected.
- Native iOS 26.5 iPhone 17 simulator host integration: **1 passed** with actual
  Capacitor WKWebView/Swift plugins and the isolated FastAPI/PostgreSQL stack.
  The expired account with a legacy avatar saves, starts a new cooldown, retains
  the name after WebView reload, updates Home, and invokes supported StoreKit.
  The dedicated name-change timestamp is identical before/after review. Native
  verification reads the server ledger before and after the supported StoreKit
  invocation, clears only the WebView consumption cache, and confirms reloading
  Home preserves the same server claim and native consumed-account guard. This
  never clears the backend ledger. The PostgreSQL review suite was rerun separately:
  **17 passed**, including competing-device claims.
  window images were attached to the passing XCTest result bundle. Apple-controlled
  review display/submission is not asserted. Physical iPhone: **not performed**.
  A separate temporary review-check project was prepared; device installation
  awaits the owner's answer to the optional physical-device test request. The
  installed CFFB app has not been changed.
- Production records/config/migrations/release checks: not performed or changed.
- Bruno definitions prepared; Bruno GUI collection execution not performed.

### Repeatable local native verification

`web/ios/tests/AccountSettingsNativeTests.swift` is a development host test,
excluded from the production App target. Its helper
`web/ios/tests/prepare-local-settings-harness.py` creates a disposable Xcode
project with local transport settings and a unique local account; it never edits
production targets or resets a consumed review account. It requires an isolated
database accepted by `scripts/seed_name_change_e2e.py`, migrated to 0117, and an
API on `127.0.0.1:18437` with `CORS_ORIGINS=capacitor://localhost`, review enabled,
and email/beta access disabled only for that local runtime. Repeated fresh-account
checks used `AUTH_SIGNUP_RATE_LIMIT=100` in this isolated runtime; production
authentication limits were not changed.

Build/copy the development bundle with `VITE_API_BASE_URL=http://127.0.0.1:18437`
and the existing OneSignal alignment script. Supply the isolated database URL as
`CFF_NAME_CHANGE_E2E_DATABASE_URL` when running the helper with the repository's
Python environment. Run the printed project's `NativeChecks` scheme with
`xcodebuild test`, an isolated simulator destination, disposable derived-data
and result-bundle paths, and `CODE_SIGNING_ALLOWED=NO`. No archive is produced.
The test seeds a cached access-token session, then exercises the real native
AuthProvider bootstrap, Settings and StoreKit bridge; Keychain refresh restoration
and physical-device gestures remain separate checks.

## Combined-release steps — do not execute yet

1. Finish the owner's remaining New Build items in this same workspace. Re-run
   relevant combined checks and review the full diff. Obtain explicit combined
   release authorization before any external mutation.
2. Back up the release database, verify the current head, and apply additive
   migration `0117_app_review_request` as part of the authorized combined rollout.
   Deploy aligned API/web/worker revisions. Keep the review switch disabled first.
3. Package the final native frontend with the **production API URL** using the
   repository's normal `npm --prefix web run ios:sync`; local verification bundles
   point at localhost and must never be uploaded. Use the existing OneSignal iOS
   15 alignment script. No version/build bump or archive was made for these items.
4. Verify Settings and restored sessions on a physical iPhone and the combined
   release candidate. Verify StoreKit invocation with development accounts;
   TestFlight's lack of a dialog does not prove failure. Keep production account
   consumption isolated from development testing.
5. Enable `IOS_APP_REVIEW_ENABLED=true` only as explicitly approved for the New
   Build rollout, on all API replicas. Release/upload together only when authorized.
6. Rollback: disable the review flag and roll application code back; **preserve
   the ledger columns and consumed rows**. Migration 0117 refuses a destructive
   downgrade once claims exist. Never reset either feature's account timestamps.

## Item 4 — native iOS phone notifications

**Implemented locally; actual APNs and signed distribution verification pending.**
See `docs/operations/native-ios-push.md` for confirmed failures, file groups,
recipient rules, exact prerequisites, permission/privacy limits and rollout order.

The existing OneSignal/Capacitor pipeline now registers authenticated installations,
handles rotation, multiple phones, scoped logout/account switch, native authorization
and Settings, pending/failed/provisional registration, App Review coordination,
validated cold-launch taps and single foreground presentation. Independent phone
categories preserve email settings; major news defaults off. A protected admin
preview/confirmation path produces durable events. Authoritative draft/matchup
and confirmed worsening roster injuries feed per-device delivery attempts, with
expiry, bounded retries, provider idempotency, current access/preferences checks,
invalid-token retirement and unread badges. Application group and service extension
are prepared; extension privacy behavior needs signed physical testing.

Verification (2026-10-13):
- Full React suite: **584 tests, 92 files passed**; TypeScript app/test/Vite
  checks and the local web development artifact build passed.
- Combined API injury/push/review/name checks: **116 passed, 3 PostgreSQL-only
  checks skipped** on SQLite. PostgreSQL push/review/name-change regressions:
  **59 passed**, including simultaneous workers and App Review claim races.
  Final native-only PostgreSQL verification: **28 passed**.
  Final privacy-fallback/slow-dispatch checks: **52 passed, 1 PostgreSQL-only
  concurrent-worker check skipped** on SQLite.
- Native Debug and Release unsigned simulator builds, including the OneSignal
  extension: passed. Device Release build settings confirm production APNs and
  existing bundle/team; no signed provisioning or physical delivery verified.
- Pure Swift: **9 privacy assertions** (recipient, logout, switch, expiry,
  malformed/fractional/boolean/infinite metadata) and **12 App Review policy
  assertions** passed. Private notification copy is promoted only after native
  account/expiry checks; OS extension bypass retains generic visible copy.
- Local desktop 1280px and mobile browser 390px: **4 passed**, real announcement
  preview/confirm with delivery disabled, dated verified injury replay, source links,
  player cards, refresh-failure cache retention and no horizontal overflow.
- Migration 0118: full PostgreSQL history, populated predecessor upgrade,
  preferences/email preservation, no historical push replay, indexes/FK,
  unused-ledger downgrade/re-upgrade, used-ledger rollback refusal and zero model
  drift all passed. `scripts/certify_native_push_migration.py` is repeatable and
  restricted to disposable localhost PostgreSQL.

Device inventory found a paired iPhone 15 with Developer Mode enabled, but its
connection tunnel was unavailable. No physical app was installed or launched.

Not performed: real APNs on an authorized iPhone (foreground/background/terminated),
provider credentials/configuration inspection, sandbox/production provider acceptance,
signed development/distribution entitlements/profiles, installation on a physical
phone, TestFlight or release. Simulator/mocks do not prove remote delivery.
Version/build remain 1.0.3/37. No production broadcasts or test alerts were sent.

## Item 5 — sourced P4 injury coverage

**Local correction and audit; production refresh held.** Public catalog audit:
815 records, 803 P4 (SEC 191, Big Ten 216, ACC 204, Big 12 192); Notre Dame excluded.
Reviewed 1,846 dated official archive rows. The safe Week 6 plan contains **86**
unique matched reports: 50 OUT, 22 FULL and 14 QUESTIONABLE. A USC Trent Mosley
report cannot be assigned because catalog IDs 251 and 1881 both match WR/name/school.
It remains unassigned; neither record was guessed healthy or injured. Upcoming
reports were pending at audit time. Missing reports do not establish health.

Evidence and the staged, dated plan:
`docs/operations/p4-injury-audit-2026-10-13.json`. `writes_performed=0` refers to
production; 86 baseline records were loaded only into the isolated local inventory.
No mass injury alerts were generated from the first snapshot.

One shared current-season/week injury feed now drives cards, draft/player lists,
roster, matchup and Injury Center. Newest same-week status wins, FULL clears prior
OUT, future/ordinary previous-week absences cannot leak into this week, and confirmed
season-ending designations persist. D/P/status variants retain their meaning.
Injury Center shows dated sourced data, pending/error states, cached refresh failures
and usable desktop/mobile card links. Phone taps retain validated league context.

Current official-report scheduling is Wednesday/Sunday at 10 AM Eastern; it may
miss reports published later that day. A five-second notification worker does not
make this feed real-time. No scheduler/production data was updated. Scoped live
connection approval was requested after automatic approval review rejected the
credential-bearing Railway variables read; that approval remains unanswered.

## Item 6 — weekly projection/actual/value charts

**Implemented and verified locally; production repair and native release remain held.**
Completed actuals/value history render solid blue; one upcoming forecast is white
and dotted. Actuals retain their own week, original pregame inputs are captured by
the worker, and missing/delayed/byes remain honest gaps. Zero/negative totals,
precise tooltips, selected week, tab and scroll survive background refresh.

The publisher processes every eligible QB/RB/WR/TE/K player through keyset batches,
including unrostered/injured/unviewed players. Known unfinished catalog games block
publication even when all starters' matchups have ended. Week 0 game selection is
shared with scoring. Verified final game facts can repair missing weekly chart
facts without writing weekly statistics, matchup scores or standings. Individual
failures and real flat recomputations are audited; corrections retain frozen
rules, forecasts, historical input/peer context and newer current values.

The original `universal_v2` weights are preserved. New calculations use the approved
game catalog for peers; historical peer lists are retained. Weekly versus season
forecast units are consistent, FULL/season-out statuses use canonical availability
categories, Week 12/13 use their correct weights, and earlier/past-season inputs
are never rebuilt from the current catalog when context is unavailable. Migration
**0119** supplies actual/value context/audits; **0121** supplies pregame snapshots.
Both are staged for the combined migration chain and protect populated history on
rollback. Only the owned local verification database received 0121.

Verification on October 14:

- Backend chart/value/outlook + existing game-selection/season-rank/ESPN scoring:
  **109 passed**.
- Final PostgreSQL chart/value/outlook suite: **55 passed**.
- Full React: **601 tests across 95 files passed**. TypeScript and local web build
  passed; no native app build was created.
- Desktop 1280px/mobile 390px Chromium: **2 passed**, with explicit synthetic chart
  fixtures and a synthetic shell session. Real public local API smoke checks also
  passed; these are not physical-iPhone/provider completeness tests.
- Synthetic **815-player** catalog: 815 pregame snapshots, 815 actuals and 815 value
  calculations; all positions, batching, retries, correction and idempotence.
  Local-only CLI replay produced five unique actual/value snapshots across five
  positions and preserved them on rerun.
- Migrations 0119/0121: full-chain upgrade, preservation/no implicit backfill,
  unused rollback/re-upgrade, populated actual/pregame rollback refusal and zero
  ORM drift passed.
- Public read-only audit: **815/815** charts fetched, **0** players with actual
  points, all with multiple forecasts and missing finality metadata, values only
  at Weeks 1/3. Current paginated inventory independently matched all 815 IDs.
  **Production data remains unchanged by this work.**
- Owned local source-backed audit: 816 eligible records (one fixture), no finalized
  weeks and zero weekly chart records before/after. No actuals were invented.

See `docs/operations/player-chart-publication.md` for the exact formula, complete
flow, files, evidence, source limitations and staged rollout/repair steps. The
public coverage evidence is `player-chart-audit-2026-10-14.json`; the read-only local
coverage evidence is `player-chart-local-audit-2026-10-14.json`. Privileged source/
finality validation, unrecoverable historical cutoffs and physical-iPhone checks
remain outstanding. No push, merge, production migration/backfill/deploy,
TestFlight upload or App Store release occurred.

## Remaining New Build requests

Draft ordering and full-player stat coverage are implemented and tested locally.
See the current draft status below and the player-stats audit. Production injury
refresh, source-rank gaps, installed-phone UI restoration and physical APNs
verification remain held/unverified. Follow the same combined release hold.


## Latest continuation — native push and installed iPhone UI

The new charcoal/blue UI with full-height sidebar and positional player headers
is retained in this workspace. The read-only website audit found the same
full-height sidebar at both public hostnames, serving identical assets with
normal HTML revalidation headers. Public API/web runtime reports commit
`a709a5afdb93bd239416efaa1a2aec522378d3b6`, migration 0116. No live changes were made.

The owner confirmed the reported old UI is in the **installed iPhone app**.
`web/capacitor.config.ts` packages `dist/spa` and has no hosted `server.url`.
The website, local frontend output and packaged native assets have separate
asset fingerprints; changing the website cannot replace an installed signed
app's UI. Both local native/web bundles retain the full-height sidebar. The
phone's actual installed version has **not** been established: CoreDevice
reported the paired phone tunnel unavailable, and the scoped CFFB app-metadata
query failed because the device was unreachable. Requested connection/unlock
or the installed version/build. A previous-build installation, TestFlight/App
Store replacement, or another installed package is a possible explanation,
not a confirmed cause. Do not claim a rollback or cache cause without evidence.

Latest push continuation closes an additional foreground-expiry gap: recipient
matching alone could permit a provider-accepted alert after its lifetime expired.
Foreground presentation now shares the native extension's recipient/finite-expiry
checks and drops expired alerts exactly at the boundary. Focused current push,
review and name backend checks: **87 passed, 3 PostgreSQL-only skipped**.
Focused native push/preferences/review frontend checks: **47 passed**, including
eight new expiry/metadata regressions; TypeScript checks passed. Prior physical
APNs/provider/signing limitations and PostgreSQL results above remain applicable.

The browser-verification attempt was initially blocked by an approval-review
usage limit. After that limit reset, the retry executed but its earlier localhost
preview was no longer listening. That failed run supplies no visual proof.
A fresh local preview/API were started for subsequent verification. Nothing has
been pushed, merged, deployed, broadcast, installed on the phone, archived,
uploaded or released; version/build remain 1.0.3 (37).

The restarted browser suite found and corrected a remaining frontend year gate:
`PlayerCardModal` hid all historical game rows even when the API returned them.
Verified game rows now render for the selected season. Actual source-backed Alex
Perry 2025 browser checks passed at **1280px and 390px**: 13 FIU games, 56 catches,
840 yards, 9 TD; Sam Houston 7/140/2; bowl 3/24/0; no document overflow. Desktop
sidebar matches the 900px viewport and its final navigation item reaches the bottom.

Phone connection update: the newly connected device is a separate iPhone from
the earlier unavailable entry. Its tunnel was acquired, but the exact CFFB app
query was blocked by **Developer Mode disabled**. No build/version was returned
and no installation/launch occurred. Requested TestFlight version/build or App
Store provenance. Apple's public lookup currently lists App Store **1.0.2**,
released **2026-10-04**, before UI changes committed October 12/13. This supports
a possible older Store package; it does not establish what is installed.

Final frontend verification after the foreground-expiry and historical-row fixes:
**585 tests across 94 files passed**, all TypeScript checks passed, and the local
web development artifact build passed. Native Swift privacy policy rechecked
with the existing standalone assertions; no iPhone binary was created. Installed
phone UI diagnosis and exact restoration gate are in
`docs/operations/installed-iphone-ui.md`.

Current native-only PostgreSQL suite rechecked after this continuation:
**28 passed**, including multi-device ownership, worker deduplication, retries,
expiry and current eligibility. Standalone Swift privacy assertions passed.
Native push repository work is verified; actual APNs display and installed iPhone
UI restoration are not claimed. The phone's TestFlight/App Store provenance
question is pending.


## Draft ordering — implemented and verified locally

- [x] Preserve established weighted positional-value policy; golden replay of all
  815 source players verifies old talent/score values to 0.001.
- [x] One versioned backend rank for real/mock/default auto-pick, full-pool sorting
  before pagination and legal player selection beyond candidate 500.
- [x] Explicit numeric rank/observed-ADP/season-or-remaining-point sorts, missing
  source rank last, genuine zero retained, deterministic IDs and source labels.
- [x] Matching real/mock settings parity, conference/scoring context, current-week
  supplementary projections, canceled stale requests, mixed-page/duplicate guards.
- [x] Source-dependent bounded cache, foreground 60-second refresh, failed-refresh
  retention, stable selected cards/picks and deliberate mock queue precedence.
- [x] Correct twelve-game season-only fallback without changing published-week
  forecasts or the existing bounded verified-game form adjustment.
- [x] Full public audit: 815 eligible / 811 source-ranked / 4 unranked, no observed
  ADP, no duplicate eligible identities; source gaps explicitly retained.
- [x] SQLite draft/ranking/room/mock/positional-card 113 passed; React 590 tests/94 files passed;
  Focused ranking regression 21 passed; PostgreSQL ranking contract 21 passed
  after correcting test teardown order;
  TypeScript passed. Actual local API pagination returns 816 unique rows (one
  local fixture), one version/current week and continuous master ranks.
- [x] Chromium local fixture browser checks 8 passed: real/mock 1440px/390px sorts,
  search/master labels, zero, open-card ID on refresh, draft ID, queue, timers,
  completed picks, reconnect/conflict handling and mobile centering.
- [ ] Authoritative source ranks for the four unranked players and observed ADP
  remain unavailable; no invented data or production repair.
- [ ] Signed physical-iPhone draft verification and the combined release remain
  held. No ranking migration required; existing migrations stay local.

Detailed policy, root causes, evidence and limitations:
`docs/operations/draft-ranking-contract.md` and
`docs/operations/draft-ranking-audit-2026-10-13.json`.

## Latest priority — Alex Perry stats (October 14)

- [x] Stable player 1082 / ESPN 5084133; 2025 FIU history retained under FIU,
  separately from the current Illinois identity and 2026 schedule.
- [x] Historical rows render; default card game log opens the latest recorded
  production when a newer schedule has no individual stats.
- [x] All 13 games and 56 REC / 840 receiving yards / 9 TD verified. All five
  screenshot lines checked exactly; genuine bowl TD zero remains zero.
- [x] 22 backend tests and two actual-public-API browser checks passed at
  1280px/390px. Shell authentication is simulated; player stats are not mocked.
- [x] Existing positional header colors/full-height sidebar preserved. No native
  build or live publication performed.
- [ ] Combined-release migration/import/publication remains held. This local fix
  is not claimed as installed-phone or production delivery.
- [ ] Remaining full-catalog source/kicker validation, new UI delivery, physical
  notifications and chart tasks are queued; the owner requested Alex first.

Evidence and root cause: `docs/operations/alex-perry-stats.md`.

## October 14 — completed UI-only local iPhone restoration

- [x] Xcode updated to 27.0; physical phone Developer Mode, connectivity and
  developer-account sign-in confirmed.
- [x] Installed CFFB changed from 1.0.2 (36) to signed local 1.0.3 (37) under the
  existing bundle/team, without uninstalling. Its signing profile includes this
  phone, code-sign verification passes, and launch succeeds.
- [x] Physically observed the charcoal/blue authenticated homepage. Existing
  sign-in survived. The outdated Pick 6 homepage promotion remains removed.
- [x] Three sidebar/player-card browser checks and four guest/authenticated
  desktop/mobile homepage checks passed against the separate restoration package.
  All 141 installed-package UI assets match its fresh tested build.
- [ ] Combined feature release, backend migrations/imports and physical APNs
  delivery remain separate. The restoration uses UI revision `9d26658` plus the
  existing homepage promo removal, compatible with the current public API. All
  combined source changes are preserved; they were not shipped by this UI restore.

No production API/database/worker change or App Store/TestFlight release occurred.
Details: `docs/operations/installed-iphone-ui.md`.

## October 14 — applied Matchup record colors and native push verification

- [x] Matchup-only full win count green / full loss count red for both teams,
  preserving inline W-L-T layout. Pending, failed, tie, bye and historical results
  remain neutral. No count increments originate from this feature.
- [x] Exact result/record receipt is written by existing standings writers in the
  same transaction. Corrections must be applied before colors update. Nullable
  migration 0122 does not invent certification for legacy rows.
- [x] Existing display-week rollover clears colors on an already-open page;
  reload/foreground preserves eligibility. League/season/week/matchup request
  guards, aborts and expired response checks prevent stale colors.
- [x] Native enabled state requires a complete positive registration response
  for the current user, iOS and OneSignal. The existing native foreground listener
  refreshes query focus without duplicate listeners.
- [x] SQLite 123 passed / one skipped; PostgreSQL 69 passed plus one subsequent
  legacy writer test; React 628 passed across 97 files; TypeScript passed.
  Chromium Matchup fixture checks passed at 1280px/390px (two tests).
- [x] Disposable PostgreSQL 0122 full migration chain/downgrade/re-upgrade and
  ORM parity passed. No production or browser database migrated.
- [x] Final canonical UI synced into a signed local development iOS app with the
  existing public OneSignal App ID. Main app development APNs, shared groups and
  phone provisioning in both main/extension profiles verified; code signatures
  passed. All 143 canonical UI files match and all 145 Capacitor resources match
  the final package.
- [ ] Physical APNs delivery remains unverified. The checkout has no server key;
  production provider/APNs readiness has not been established. The paired iPhone
  currently reports unavailable. No test push was sent.
- [ ] Combined backend/native release remains held; this complete local package
  was not installed over the live-compatible UI-only restoration. No production
  migration, deployment, push/merge, TestFlight/App Store upload or public release.

Implementation and limits: `docs/operations/matchup-record-highlights.md` and
`docs/operations/native-ios-push.md`.

## October 14 — remove Big Plays completely from active notifications

- [x] Remove Big Plays, long rush/reception/pass controls from global and league
  Settings. Remove retired preference keys from the API schema and strip old API
  keys before frontend saves. Existing columns are inert compatibility storage.
- [x] Delete ESPN play-text alert extraction, accepted-snapshot fanout and typed
  play intake. The active registry cannot enqueue Big Play, long-play or old
  touchdown events, even if the legacy injury CLI flag is true.
- [x] Cancel old queued play events before rendering/fanout/provider calls; hide
  old play history, unread counts and badge contributions; deny old push
  destinations. Keep audit data and other notification categories intact.
- [x] SQLite notification/registry/ESPN scoring/native push/provider checks:
  130 passed, one PostgreSQL-only concurrency check skipped. Disposable
  PostgreSQL notification checks: 25 passed.
- [x] Chromium fixture Settings checks passed at 1280px/390px (two tests),
  including old API payloads, absent controls, remaining global/league saves,
  reload and no page overflow, at `http://127.0.0.1:18448/settings`.
  Authentication and notification payloads were fixtures; no production calls.
- [x] Local web build passed. No native rebuild, installation, deployment,
  migration, push/merge or TestFlight/App Store upload for this removal.
- [x] Final frontend suite: 628 passed across 97 files; application, test and
  Vite TypeScript checks passed. The built Settings chunk contains none of the
  retired Big Plays/long rush/reception/pass labels.

Focused regressions: `tests/api/test_notifications.py`,
`tests/api/test_espn_live_scoring.py`,
`web/client/components/NotificationSettingsPanel.spec.tsx` and
`web/tests/e2e/settings-without-play-alerts.spec.ts`.

## October 14 — notification finalization readiness

- [x] Read-only live metadata confirms API and notification worker both run
  `a709a5afdb93bd239416efaa1a2aec522378d3b6`, preceding these combined changes.
- [x] Presence-only remote check: worker OneSignal push enabled, expected public
  App ID matches and server key present; API has push/provider unset, no server
  key and no matching App ID. This is a concrete registration/configuration gap.
  No secret values printed, copied or persisted; no production write performed.
- [x] Final local native package rebuilt after Big Plays removal. Code signatures
  passed; main development APNs and main/extension shared groups verified. All
  143 canonical UI files match, and all 145 clean synced resources match the
  signed package. Removed only seven untracked duplicate generated resources.
- [ ] Existing OneSignal Apple push setup requires owner dashboard sign-in.
  App key validity and real APNs delivery are not yet established.
- [ ] Paired physical iPhone still unavailable; no full combined app installed.
- [ ] API/worker code, configuration and migration rollout remain under the
  owner's combined-release hold. No standalone notification deployment,
  migration, broadcast/test push or TestFlight/App Store upload occurred.

### Owner connected the phone and signed in — subsequent checks

- [x] Phone connection confirmed. Current CFFB query returns **1.0.2 (36)**,
  superseding the earlier installed-version observation. The reason for that
  change is unknown; no app installation/uninstallation in this check.
- [x] OneSignal Apple APNs active with existing `.p8`, matching bundle and Team ID
  `84TV35F6T5`. No key exposed or provider configuration changed.
- [x] Live API health/readiness/runtime all HTTP 200; database reachable, deployed
  schema 0116 and prior commit unchanged. Unauthenticated registration HTTP 401.
- [ ] Live native-push contract still incompatible: no installation/account/App
  ID/environment registration fields, no `delivery_configured` acknowledgement,
  and no owned event-open endpoint. Combined code/schema/configuration deployment
  and installation must precede the physical delivery test.
- [ ] Owner's explicit combined-release authorization remains unresolved. Device
  connection and dashboard sign-in do not silently revoke that release hold.

## Combined rollout authorized October 14

The owner explicitly answered yes to the combined API/worker update, production
migrations and physical iPhone installation. This supersedes the earlier hold for
those actions. No App Store/TestFlight upload is included in this authorization.

- [x] Full backend suite with required repository import path and localhost
  permission: 1,166 passed, three environment-specific skips. Initial four
  failures were subprocess import/socket environment issues, resolved without
  changing tests or application code.
- [x] Existing frontend verification remains 628 passed, TypeScript and desktop/
  mobile Settings checks passed. Combined native build incremented to 38.
- [x] Private pre-migration production backup secured, 77,263,042 bytes, SHA256
  `0becdd646b75cb63c66f7e48c979594326412d76d680ac80b6d2cc42c051ce59`.
  Backup is outside the repository with owner-only permissions.
- [x] Production backup restored and upgraded 0116 → 0122 on disposable
  PostgreSQL 18 matching production. Core data counts and row digests preserved:
  users 105, leagues 52, teams 94, roster entries 494, players 818, player stats
  3,156, standings 314, matchups 225 and draft picks 494. ORM parity passed.
- [x] PR #393 merged as `a7f2fcda51cd61b4d8346378723b87419cc00a1d` after
  all exact-head checks passed. API, notification, lifecycle and scoring workers
  successfully rolled to this revision.
- [x] Existing official injury scheduler updated to the same merged revision;
  deployment `222a5bdf-1e90-4cbb-9c76-315a6e893117` succeeded. Its production
  cadence remains daily at 10 AM America/New_York, rather than the unapplied
  repository Wednesday/Sunday cron configuration.
- [x] API references the worker's existing OneSignal key without copying or
  exposing it. Presence-only checks confirm enabled push, OneSignal provider,
  matching App ID and resolved server credentials on API and notification worker.
- [x] Production migrations reached 0122. Public readiness, migration-head check
  and Alembic ORM parity passed. All nine audited core table counts match the
  protected backup. Notification processor heartbeat is healthy, with zero retries
  and dead letters after migration recovery.
- [x] Native registration fields and `delivery_configured` acknowledgement are
  live, along with the owned-event tap endpoint.
- [x] Final signed development package 1.0.3 (38) passes signature verification;
  all 143 canonical UI files match the package, plus only two Cordova resources.
- [ ] Install build 38 and verify real scoped iPhone delivery. The device became
  unavailable before installation; reconnection and unlock requested. No physical
  delivery, distribution APNs or App Store/TestFlight release is claimed.

Railway initially stalled the API build waiting for a build slot. Retrying from
the same merged source succeeded while the old API continued serving traffic.
The new notification worker briefly reported missing `expires_at` before the API
startup migration completed; its subsequent healthy heartbeat verifies recovery.
Automatic approval review rejected stopping the previous worker before its
replacement was verified. That action did not execute; rolling replacement was
used instead.

## App Review activation — October 14

The owner requested one automatic native App Store review opportunity on each
account's next login, with no later repeat. The existing implementation already
matches this contract; its disabled production feature switch was the blocker.
`IOS_APP_REVIEW_ENABLED=true` was applied to the API, and the verified merged
source was rolled as deployment `5d7c831e-bf71-4996-a018-4847f7a985e7`. The public
runtime endpoint now reports the switch enabled and readiness at revision 0122.
No implementation changes, additional native build or eligibility reset was needed.

The next confirmed native iOS login or restored session becomes eligible after
onboarding and roughly three unobstructed seconds on a usable safe screen.
StoreKit is invoked only after the authenticated atomic database claim commits.
Dismissal, Apple suppression, reinstall, another device and later logins do not
reset the immutable account's lifetime consumed state. Browsers do not consume it.
Apple controls actual display; a native request cannot guarantee a visible popup,
and TestFlight does not display this review request.

Reverification: all 17 review backend tests passed on an isolated PostgreSQL 18
database, including simultaneous devices receiving exactly one authorization;
all 56 coordinator/frontend tests passed; all 12 Swift native policy assertions
passed. Disposable data and the local PostgreSQL process were cleaned up.
The production pre-activation read found 105 accounts and zero consumed review
authorizations; no test claimed or reset any production account.

Build 1.0.3 (38) already contains the native coordinator/plugin. Physical iPhone
installation and review display remain unverified because the device is
unavailable. No App Store/TestFlight upload occurred.

## Weekly Challenges — local combined-release hold (October 15)

This section is separate from the earlier notification/review production rollout.
Weekly Challenges remains an uncommitted local implementation on
`codex/weekly-challenges`, based on merged revision `a7f2fcd`. No push, merge,
production migration/deployment, native sync/build, or TestFlight/App Store upload
was performed for it. All new feature files are staged for the eventual combined
release; generated `config 2.xml` remains excluded.

- [x] All five free formats: Slate 12, Upset Hunter, Fantasy Five, Lock of the Week,
  Rivalry Duels. Home entry and leaderboard actions, exactly five hub cards,
  account-scoped entry recovery, history, results, public profiles and recognition.
  Sidebar/bottom navigation and unrelated membership behavior are preserved.
- [x] Server-enforced shared five-minute cutoff, sticky closure, started-game guard,
  one revisioned official entry, atomic cross-role duel seats, authorization,
  hidden opponent choices and persisted mutation limits.
- [x] Existing canonical games/approved player pool, fantasy engine, JWT auth,
  SQLAlchemy database and lifecycle worker reused. Published rules/slates frozen;
  source/version fingerprints, correction audit ledger and idempotent awards.
- [x] Shared Matchup display rollover is Wednesday 00:00 America/New_York,
  following the existing Tuesday 08:00 operational reset. Fixed the early-Tuesday
  double-offset edge case. DST-safe tests preserve league fallback behavior.
  Every new round starts with fresh entry slots; it never relabels the old slate.
  Published future rounds remain Upcoming until the canonical week reaches them.
- [x] Migration `0123_weekly_challenges` follows `0122_matchup_record_application`.
  Local PostgreSQL 18 upgrade/check/downgrade/re-upgrade/check passed. A second
  nonempty-history downgrade check correctly refused destructive rollback;
  schema head and all six controlled preview entries remained intact. Local
  `/health/ready` reports database/migrations ready at 0123.
- [x] Full frontend: 98 files, 636 tests passed. App/test/Vite type checks and
  local Vite build passed. No standalone lint command is configured.
- [x] Final full backend: 1,218 passed, five skipped (environment-specific tests),
  with existing deprecation warnings. PostgreSQL 18 challenge/calendar suite:
  all 64 passed, including simultaneous entry submissions and cross-role duel
  accepts; no skips. The two concurrency cases skipped by SQLite run on
  PostgreSQL. Final working-tree and staged `git diff --check` passed.
- [x] Real local browser checks at desktop 1280×720 and mobile 390×844: Home links,
  five-card hub, administrator configuration/validation/publication, draft save,
  official submit/edit/reload, every format's selections, duel invitation/
  acceptance/privacy, rejected empty entry, expired stale-screen write,
  missing-stat Processing, final results, provisional/final standings and profile
  badges. Mobile document width matched its viewport, with no horizontal overflow.
  Temporary viewport override was reset.
- [x] Controlled correction repeated twice: standings changed from 23/15 to 21/10
  points while the six existing award rows remained six. Preview outcomes,
  players and users are local fixtures, never production participants/winners.
- [x] Nineteen Bruno requests prepared. Bruno CLI is unavailable here; those files
  were not executed as a Bruno collection. The corresponding API routes were
  exercised by automated tests and the real local browser.
- [ ] Publish actual weekly slates during the approved combined release. The
  admin catalog updates from canonical weekly games and eligible players;
  administrators must choose/validate/publish the curated slate, explicit
  underdogs/difficulty values, featured game and Fantasy Five pool. Incomplete
  or expired configuration stays Upcoming rather than opening last week's picks.
- [ ] Apply 0123 in production and deliver the matching bundle in the approved
  combined native release. Physical iPhone/production challenge verification
  remains pending that release. No new native package contains this feature yet.

Evidence and operation/API details: `docs/operations/weekly-challenges.md`.
Local preview: `http://127.0.0.1:18458/weekly-challenges` with API port 18457.
Screenshots are in `/private/tmp/cff-weekly-challenges-evidence/`:
`desktop-final-hub.png`, `mobile-provisional-leaderboard.png`, and
`mobile-final-leaderboard.png`. These are controlled local test data.

## 1.03 update walkthrough and final feature checks — October 15

- [x] Centered ten-screen update walkthrough, personalized greeting, Next/Back,
  progress, Skip/Close/Got it. Once per authenticated account/release across
  reinstall and other devices; no repeat after dismissal or unfinished viewing.
- [x] Onboarding → update walkthrough → native App Review ordering. No collision
  with existing dialogs, stale-account responses, or native permission requests.
  App Review's lifetime claim remains independent.
- [x] Next confirmed iOS login or restored session requests Apple's native rating
  sheet for each account that has never consumed its review opportunity. The
  system sheet supplies the tappable 1–5 stars and App Store submission; no custom
  rating gate or duplicate prompt. Dismissal consumes the opportunity, and the
  combined build must preserve existing claims across versions and devices.
  Apple decides whether to display the sheet; TestFlight cannot verify display.
- [x] Additive migration `0124_release_notice` after Weekly Challenges 0123,
  locally upgraded/checked/empty-downgraded/re-upgraded/checked. Once-only receipts
  block nonempty downgrade; existing users/entries preserved. Production remains
  at 0122 and is untouched.
- [x] Real local Settings name change confirmed and persisted after reload;
  seven-day lock shown. Direct API cooldown rejection did not restart the clock.
  Notification category changes persisted; Big Play controls/API keys absent.
- [x] Real local API → worker → Alerts history/unread → Mark All Read verified
  using isolated fixtures and fake external providers; no phone/email contacted.
  Fixed diagnostic-only no-league 500 and multiple-league scalar ambiguity, with
  regression coverage. No normal event rules or production admin gate changed.
- [x] CoreDevice read confirms the connected iPhone still has **1.0.2 (36)**.
  It has not received the newer combined UI/push implementation. No app was
  installed/uninstalled, and no native build or distribution upload occurred.
- [ ] Physical APNs banner/background/tap and updated native UI verification await
  installation of the matching combined package. Do not present server/mocked
  delivery as proof of iPhone display. Prior signed build 38 predates the newly
  staged Weekly Challenges and update walkthrough.

Operation/contracts/evidence: `docs/operations/update-103-walkthrough.md`.

Final regression results: **1,225 backend passed / 6 skipped**, **649 frontend
passed**; dedicated PostgreSQL **86 notification tests** and **43 update/App
Review/name-change tests** passed without skips. Type checks, local Vite build,
migration parity/history guard and diff checks passed. Standalone Swift policy
checks passed 12 App Review and nine notification-privacy assertions; no native
app package was built. Actual local browser evidence also confirms the WR header
gradient, full-height sidebar, persisted Settings state and in-app badge clearing.

## Combined iPhone test rollout authorized — October 15

The owner requested installation on the connected iPhone and explicitly approved
deploying the combined backend for testing. This supersedes the local-only hold
for the combined source push/merge, migrations 0123/0124, API/worker deployment,
and native build/install. App Store/TestFlight upload and submission remain held
until the owner completes phone testing. The new test package is 1.0.3 (39),
including the matching notification extension; build 38 is superseded.

The prepared release has 1,225 passing backend tests, 649 passing frontend tests,
and dedicated PostgreSQL notification, review, name-change and challenge checks.
Production backup, migration rehearsal, exact-source CI, deployed readiness and
the installed version must be verified during this rollout. No production review
claims or update receipts may be reset to manufacture repeat prompts.

### Installed test release — October 15

- PR #394 merged as `842c070b342222ac17861f3952a4c319363501fc` after all
  exact-head checks passed, including both real-stack workflows. The sign-up
  browser regression now completes the genuine ten-step walkthrough before
  signing out and checks that it stays dismissed after reload/login. Its isolated
  local run passed; no production UI behavior was disabled to satisfy the test.
- Owner-only production backups remain outside Git. The initial backup was
  restored into a separate localhost PostgreSQL 18 database; 0122 → 0124 and ORM
  parity passed with identical counts/digests for all nine audited core tables,
  no pre-consumed update receipts and no challenge entries. A fresh backup was
  also taken immediately during rollout after the earlier session's delay.
- API deployment `09997fe0-7308-4c9a-b1df-b9e88aec6aa1`, notification worker
  `542d6e35-557e-4a7e-b455-ebb7c1d73688`, lifecycle worker
  `4dbe26fb-9b10-4db3-bd6d-59ea6c8f1cfe`, and scoring worker
  `835f0ce7-f8f8-4fe4-9530-d1e8a1e7590b` all succeeded on the merged source.
  Live readiness reports 0124, all public runtime SHA fields match the release,
  the existing database identity is unchanged, and all continuous worker
  heartbeats are healthy. The new challenge/update endpoints are in live OpenAPI.
- The development-signed app and notification extension are **1.0.3 (39)**.
  Signature verification passed; all 144 canonical production-targeted web files
  match the installed package, with only generated Cordova resources added.
  APNs development and shared notification-group entitlements are present.
- CoreDevice installed over the existing CFFB app without uninstalling, confirmed
  version/build 1.0.3 (39), and successfully launched it on the physical iPhone.
  The updated Home/Weekly Challenges surface loaded against the matching API.
- Real weekly slates still require administrator configuration/validation and
  publication; the current round correctly remains Upcoming. Physical APNs
  banner/background/tap delivery and actual StoreKit display/submission are not
  certified by installation, server health or screenshots. Leave the owner's
  once-only receipts intact while testing.
- No App Store/TestFlight upload, distribution archive or submission occurred.
  Await the owner's phone-test result before proceeding to distribution.

## Home popup timing and open challenges — October 16

The owner confirmed having dismissed the automatic popup(s), explaining why the
Home screenshot showed neither. The lifetime/per-release suppression was correct.
For eligible accounts the native host now uses zero artificial presentation delay,
while authentication, onboarding, update walkthrough, modal, permission, foreground
and native scene guards remain in force. Apple still controls StoreKit display.
The owner separately authorized exactly one replay for their own test account;
this exception must be audited and must not change anyone else's eligibility.

All 650 frontend tests, application/test/Vite type checks and local Vite build
passed. Native test package increments the app and extension to 1.0.3 (40).
Week 7's five real slates were independently provider-verified, server-validated
and published through existing audited services. All five report Open; publication
scope and deadlines are in `docs/operations/week-7-challenge-publication.md`.
No App Store/TestFlight submission is authorized before the owner's test result.
