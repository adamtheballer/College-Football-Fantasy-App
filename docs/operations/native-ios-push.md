# Native iOS push — combined release held locally

Status October 14: repository implementation, isolated checks and a signed local
development app/notification extension are verified. Real physical APNs delivery
and distribution signing remain unverified. The installed phone's separate UI-only
restoration does not include these combined push changes. No production sends,
migration, deployment, push, merge, archive, upload or release occurred.

## Confirmed failures

The app uses React in Capacitor 8, Swift/iOS 15+, OneSignal Capacitor 1.1.8 and
OneSignal iOS 5.7.0, FastAPI/JWT user IDs and the existing notification outbox.
Native registration was gated by the browser permission API. Native granted
permission could be shown as enabled before the SDK subscription or backend
registration succeeded. Account teardown cleared authentication before detach,
detached all phones, and retained stale registration cache. Dispatch targeted
provider aliases rather than individual registered subscriptions; a 2xx response
without a message ID could be marked accepted. Native capabilities, application
group and notification service extension were missing. Injury ingestion wrote
in-app history without durable phone deliveries and treated note changes as events.

## Implementation and event contract

`notification_service.py`, `notification_providers.py`, `notification_events.py`,
notification models/schemas/routes and migration 0118 extend the existing ledger.
Registration requires authenticated actor, installation ID/secret hash, subscription,
app ID and native environment; provider identity is verified server-side. Scoped
logout and installation capability permit account switching without disabling other
phones. Invalid subscriptions are disabled individually. Phone category settings
are distinct from email settings; news requires explicit opt-in and admin approval.

- Draft start: existing authoritative backend transition, key per draft/recipient,
  current participant and live draft check. Pauses/resumes do not create new starts.
- Matchup start: earliest verified kickoff in the recipient team's frozen weekly
  **starter** snapshots, using existing `rebuild_matchup_start_notifications`.
  One stable matchup/recipient key; verified kickoff changes reschedule pending
  jobs and expiry. Missing/postponed kickoffs do not create reminders. Current
  matchup, week, season, ownership and membership are rechecked.
- Injury: first import establishes a baseline. Only new/worsening Q, D, OUT/IR/
  season-ending severity queues an event; P/Probable remains healthy. Stable
  availability-event/user key combines leagues; current active ownership includes
  starters, bench and IR. Dropped players are suppressed. If one league is left,
  remaining eligible ownership supplies the destination. Reports are not invented.
- News: protected admin draft, audience preview, explicit confirmation and durable
  status. Audience supports opted-in users, managers owning a conference's players,
  and/or an exact player. Recheck opt-in/audience before dispatch; no scraped feed
  broadcasts. Reading the announcement also requires eligibility.

A device delivery is unique per event/token/attempt. Existing PostgreSQL claim
leases, `FOR UPDATE SKIP LOCKED`, deterministic provider idempotency and bounded
backoff handle concurrent workers/retries. Phones installed after fanout never
replay that event. TTL defaults: draft 30 minutes, matchup 1 hour, injury 6 hours,
news 24 hours. Expired jobs and permanently invalid tokens do not retry. Existing
unread history supplies badge counts. Queued, provider-accepted, invalid-token,
expired, skipped and failed outcomes remain distinct. Acceptance is not display.

### October 14 — play alerts removed

Big Plays and its long-rush, long-reception and long-pass children are removed
from global and league Settings, request/response schemas and the active event
registry. The unused touchdown event is also retired. The ESPN play-text candidate
parser, accepted-snapshot notification producer and typed play intake are deleted;
accepted snapshots still support normal scoring and projections.

Old clients' play preference keys are ignored and cleared on preference saves;
new clients strip those keys from old API responses before saving. Existing
database columns remain inert for compatibility; no new migration is needed.
Previously queued play events are canceled before content rendering or delivery
fanout, including missing event types identified by legacy notification type or
the exact `big_play:` key prefix. Opening an old play push cannot obtain a usable
destination. Old logs are excluded before the history limit and from unread/read
operations and native badge counts; audit rows are retained.

`LIVE_PLAYER_NOTIFICATIONS_ENABLED` remains only as the existing injury-ingestion
CLI default; changing it cannot restore any play alerts. The removal is staged for
the held combined release. The installed UI-only app and live service have not
been updated by this change, and this task created no new native build.

## Native experience and privacy

`push-notifications.ts`, `PushNotificationCoordinator.tsx`, `push-navigation.ts`,
Settings and protected announcement pages implement native permission and validated
tap handling. Settings uses “Get draft reminders, matchup alerts, and injury updates
for your players.” Denied permission links to iPhone Settings without repeated
requests; foreground returns recheck authorization. Pending, failed, provisional
and unconfigured registration are distinct from enabled. App Review's presentation
blocker surrounds permission requests. Verified authentication gates SDK identity;
logout/switch invalidate outstanding work. Taps wait through session restore/login,
ask the owned-event API for current access and use existing internal routes.

`AppReviewPlugin.swift` also registers PushRuntime for authorization, Settings,
shared account binding and badges. `App.entitlements`, Info.plist, AppDelegate and
project configuration add APNs/background capability and the shared group.
`OneSignalNotificationServiceExtension` checks recipient/expiry before processing;
shared binding clears immediately on logout. The foreground SDK callback permits
one native banner only for the authenticated recipient with a finite, unexpired
server lifetime. It discards foreign, missing, malformed and expired metadata,
including the exact expiry boundary; the native extension applies the same checks.

**Platform limit:** iOS can bypass/time out the extension. The APNs visible payload
therefore uses generic CFFB copy for native phones; private league/roster title and
body are promoted from additional data only after the extension checks current
account and expiry, including a second check at its completion callback. A generic
alert shell may remain on an offline signed-out phone, but the fallback alert does
not display private league/roster text. Signed physical tests must verify this
behavior while backgrounded and terminated.
Never claim simulator/mocks establish that installed production notifications work.

## Cadence and server configuration

Existing notification worker `scripts/run_notification_worker.py` polls every five
seconds (configurable); authoritative schedulers enqueue draft/matchup events.
The committed official injury cron currently refreshes **Wednesday and Sunday at
10 AM America/New_York**. Public current reports may still be pending then. The
observed Railway cron metadata is daily paired UTC hours, but the command's weekday
and local-hour guards still limit effective refreshes. This is not real-time injury
coverage; no scheduler was changed or deployed in this task.

All API and notification-worker replicas need matching `ONESIGNAL_APP_ID` and the
server-only `ONESIGNAL_APP_API_KEY`, `PUSH_PROVIDER=onesignal`, expiration settings
and an enabled worker. Frontend public `VITE_ONESIGNAL_APP_ID` must match. Production
registration fails closed if server provider ownership verification is unavailable.
Do not enable OneSignal JWT identity-verification requirements without confirming a
compatible native SDK login integration; the pinned Capacitor login has no JWT
argument. No provider credentials were inspected or production alerts sent.

### October 14 — live service readiness checked without secret disclosure

A read-only Railway service metadata and remote environment-presence check now
establishes the actual deployment mismatch. Both API and notification worker run
`a709a5afdb93bd239416efaa1a2aec522378d3b6`, predating the combined native changes.
The notification worker has `PUSH_NOTIFICATIONS_ENABLED=true`,
`PUSH_PROVIDER=onesignal`, the matching public App ID and a server key present.
The API has neither push flag/provider configured nor a server key present; its
App ID does not match the expected public ID. No secret value was printed,
copied locally, persisted or transferred between services. No service variable,
deployment, database or worker state was modified.

Thus the owner does not need to supply a new server key. The approved combined
rollout must provide the API and notification worker with the same existing
OneSignal configuration and code/schema before native registration can succeed.
Use a protected shared/reference variable rather than putting the key in source,
frontend assets, commands or logs. Validate APNs setup in the existing OneSignal
app, then test a scoped phone subscription with the paired physical iPhone.
The OneSignal dashboard currently requires owner sign-in, and the latest device
check reports the paired phone unavailable. Real delivery remains unverified.

Subsequent owner-assisted verification on October 14 resolved dashboard access
and phone connectivity. OneSignal shows Apple iOS/APNs **Active**, existing `.p8`
authentication, bundle `org.collegefantasyfootball.app`, and Team ID `84TV35F6T5`
matching the signed local package. No authentication setting was edited or key
revealed. An active dashboard configuration does not certify actual delivery.

The connected physical phone currently reports **CFFB 1.0.2 (36)** again. This is
a new observed state after the earlier 1.0.3 (37) restoration; the reason for the
version change is not established. Do not treat it as the signed combined package.
No app was installed or uninstalled during this verification.

Live API checks returned HTTP 200 for `/health`, `/health/ready` and
`/health/runtime`; the database is reachable and at the deployed repository's
head `0116_league_conference_pool`. Native notification readiness is a separate
failure: deployed `PushTokenCreate` exposes only platform/provider/subscription,
`PushTokenRead` lacks `delivery_configured`, and `/notifications/events/{event_id}/open`
is absent. Unauthenticated registration correctly returns HTTP 401. Consequently,
the strict new native client cannot certify registration against this deployed
contract. The API/worker configuration and combined code/schema rollout are still
required; healthy endpoints alone do not establish native push support.

### October 14 registration and local package verification

Native registration now requires a complete acknowledgement: a positive token ID,
the authenticated user's ID, OneSignal/iOS, enabled state, and explicit
`delivery_configured=true`. A successful HTTP status or missing configuration flag
cannot mark native notifications enabled. Seven malformed/foreign/disabled
acknowledgement cases are covered by regression tests. Existing account epoch and
logout guards remain in place.

The coordinator's existing single native foreground listener now updates React
Query focus as well as rechecking permission. This refreshes already-open Matchup
data after foregrounding without adding a second native subscription.

The public deployed website identifies OneSignal app
`fb57b2ec-69c8-480c-a9fe-c379762c02f1`. The final local build uses that public App ID
via `VITE_ONESIGNAL_APP_ID` at build time; no provider secret is embedded or written
to an environment file. No server key/provider configuration is available in this
checkout. The subsequent presence-only service check above confirms it exists on
the live notification worker, but not on the API; validity/APNs setup remains
unverified.
Matching server configuration and OneSignal APNs credentials still require
verification before a physical isolated-account delivery can be certified.

The canonical local app was built successfully with Xcode 27, code-sign verification
passed, and the main app has `aps-environment=development`. App and notification
extension both have the matching shared group in their signatures and profiles;
both profiles include the paired phone. All 143 canonical web files exactly match
the package, and all 145 packaged files match Capacitor's synced resources (the
additional two files are generated Cordova resources). This proves the signed
package contents and capabilities, not APNs delivery. The final package was then
rebuilt after the play-alert removal and verified again: 143 canonical UI files
plus only the two generated Cordova resources, with both signed push capabilities.
Seven untracked duplicate generated resources were removed before rebuilding;
no source or installed-phone files were deleted. The last device check
reported the physical phone unavailable; the full combined app was not installed.

## Exact Apple/provider prerequisites and release sequence

1. Development provisioning is verified locally for main bundle
   `org.collegefantasyfootball.app` and extension
   `org.collegefantasyfootball.app.OneSignalNotificationServiceExtension` under
   existing team `84TV35F6T5`. Enable Push Notifications for the app and register
   `group.org.collegefantasyfootball.app.onesignal` on **both** identifiers/profiles.
   Distribution provisioning/signing must still be verified for the combined
   release; main target Debug uses development APNs, Release uses production.
2. Configure the matching OneSignal app's APNs authentication key (.p8), Apple Key
   ID and Team ID, or valid matching certificates, covering sandbox and production.
   Keep Apple signing/provider keys outside frontend code and ordinary logs.
3. Pause dispatch, retain backups and apply the reviewed combined migration chain (0117 through the final approved
   head; currently 0122). 0118 retires
   pre-rollout pending push attempts while retaining email/history. Run readiness
   and model parity checks. Deploy API/worker/frontend together **only after approval**,
   initially with push/review disabled. The separate installed UI-only package is
   1.0.3 (37); it is not the combined native-push release.
4. Start isolated native verification with a signed development app on an explicitly
   authorized physical iPhone. Check OS Settings changes, cold start, background,
   termination, token rotation, two phones, logout/switch, each event/category,
   invalid tokens, expiry, quiet hours, badge clearing and App Review non-overlap.
   Verify provider identity lookup and per-device accepted IDs against this account.
5. Separately verify signed distribution entitlements/profiles and production APNs
   using approved isolated accounts. Only then enable intended flags and authorize
   the combined archive/TestFlight/App Store steps. Never broadcast a test to users.
6. Rollback by disabling push/review on every replica and rolling back application
   code. Preserve the delivery/review ledgers; migration downgrade refuses after
   device deliveries/news/claims exist. No destructive reset of claimed accounts.

Verification results are recorded in `docs/release/new-build-checklist.md`.
Primary provider references: [Capacitor setup](https://documentation.onesignal.com/docs/en/capacitor-sdk-setup),
[subscription identity API](https://github.com/OneSignal/onesignal-node-api/blob/main/apis/DefaultApi.ts),
[Apple APNs registration](https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns).
