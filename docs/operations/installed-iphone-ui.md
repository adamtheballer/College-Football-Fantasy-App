# Installed iPhone UI — diagnosis and restoration status

**Current status (October 14): the UI restoration is installed and running on the
owner's physical iPhone as CFFB 1.0.3 (37).** The new charcoal/blue homepage is
visually confirmed, the outdated Pick 6 homepage promotion is absent, and the
existing signed-in session survived the update. This is a local development
installation; no App Store or TestFlight release occurred. The unreleased combined
statistics, ranking, charts, review and push changes remain preserved separately.

The owner confirmed the old UI is in the installed iPhone app. The new UI remains
in the canonical React source: charcoal/blue theme, a full-height sidebar whose
navigation items reach the bottom, and positional player-header gradients.

The iOS app uses Capacitor with `webDir: dist/spa` and no hosted `server.url`.
Website edits cannot replace a signed installed app's UI assets. The website,
local Vite output, and native packaged assets have separate fingerprints. No UI
selection flag or application service worker that swaps whole UI versions was
found. The OneSignal worker is a notification service worker.

Read-only observations on October 13, 2026:

- Both public website hostnames redirect to the same site and serve identical
  current assets. Their main bundle contains the full-height/stretched sidebar.
  Public API/web runtime reports commit `a709a5afdb93bd239416efaa1a2aec522378d3b6`.
- Apple's public app lookup lists App Store version **1.0.2**, released
  **October 4, 2026**, before the October 12/13 UI changes. If that is the installed
  package, the older UI is expected. This does not prove the phone's installation.
- The initially paired iPhone 15 was unavailable. The owner then connected a
  different iPhone, with the same display name. Its unique CoreDevice identifier
  was used. The connection tunnel was acquired, but the scoped CFFB app query
  failed because **Developer Mode is disabled**. No app version/build was returned.
- Requested the installed TestFlight version/build or App Store provenance.
- Local Chromium checks at 1280px and 390px passed. The desktop sidebar is exactly
  the 900px viewport height, with its last item reaching the bottom. The positional
  header and source-backed game log render without document overflow.

Do not describe a specific overwrite, rollback or cache issue as confirmed until
that installed package is identified. If the intended UI is available in an
already-authorized TestFlight build, identify that exact build for restoration.
Otherwise it needs the UI to be packaged into the eventual approved combined build;
there is no supported website-side hot patch for this installed app configuration.

At the end of the October 13 investigation, the combined release remained held. No app was launched, installed, removed,
archived, uploaded or released; no phone settings were changed. Current source
version/build remains 1.0.3 (37). Provider/APNs signing and authorized physical push
verification remain separate prerequisites documented in native-ios-push.md.

Primary source: [CFFB App Store listing](https://apps.apple.com/us/app/college-football-fantasy/id6804566813).

## Authorized local update attempt — October 14, 2026

The owner explicitly authorized refreshing the installed app with the new UI.
This permits preparing, signing and installing a local device update; it does not
establish that a combined production release or App Store upload has occurred.

`npm run ios:sync` completed against the production API URL and packaged the
current React output. An unsigned arm64 device compilation of the entire app and
OneSignal extension succeeded. Its version/build is **1.0.3 (37)**; neither was
bumped. All **142 packaged UI files** match the fresh SPA output and the compiled
`App.app/public` directory byte for byte. The packaged index SHA-256 is
`c3248b0399f02fc966d5694ee07999dcb15370c21938a7ab295af4f22614bcd7`.

Three Chromium checks against that exact production-built SPA at
`http://127.0.0.1:18449` passed: full-height member/admin navigation and the
positional player header on desktop and 390px mobile. Shell accounts and player
responses were synthetic; these checks do not prove physical phone behavior.
The player-card fixtures now reuse the existing canonical draft-pool helper and
provide explicit chart finality, matching the current client/API contract.

The signed build failed with Xcode's `No Accounts` error. Cached profiles for
both the app and notification extension lack the App Groups capability and
`group.org.collegefantasyfootball.app.onesignal`. Both paired phones still report
`unavailable`; no installed CFFB version could be queried. The correct project
was opened in Xcode. Requested developer-account sign-in and a connected,
unlocked phone with Developer Mode enabled. These are external prerequisites,
not missing user authorization. No app was installed, removed or released.

Public API compatibility was also checked without account credentials. Runtime
still reports commit `a709a5afdb93bd239416efaa1a2aec522378d3b6` and migration
`0116_league_conference_pool`. `/players` lacks the new ranking version/context;
Alex Perry's trajectory lacks explicit `is_finalized` flags. Shipping the entire
combined client alone would make these features unavailable. Restore a compatible
UI-only package or coordinate the reviewed backend migration/API release before
shipping the complete combined app. Preserve all combined source changes.

Build output: `/private/tmp/cff-new-ui-device-build/Build/Products/Debug-iphoneos/App.app`
(unsigned, not installable). Diagnostic logs: `/private/tmp/cff-ios-ui-sync.log`,
`/private/tmp/cff-new-ui-device-build.log`,
`/private/tmp/cff-new-ui-unsigned-build.log`,
`/private/tmp/cff-ios-packaged-ui-browser.log`.

## Connected phone follow-up — October 14, 2026

The wired phone is now reachable and the owner enabled Developer Mode, which
CoreDevice confirms. App inspection is blocked by developer-image mounting error
12040 / `PersonalizedBundleMissingVariantError`: the installed DDI does not
contain this physical phone's board/chip variant. The phone reports iOS 27.0.1;
the Mac has Xcode 26.6 and macOS 26.6.2. The supported component check reported no
new updates, and a non-destructive DDI refresh found an identical image set.

Apple's [Xcode requirements](https://developer.apple.com/xcode/system-requirements)
list Xcode 27 with iOS 27 SDKs and macOS 26.6 or later. Started the available
official Xcode 27 update in the Mac App Store; download progress was visibly
confirmed. Completion and a successful DDI mount are not yet established.

The signing retry still failed with `No Accounts` and missing App Group profiles.
Added the extension's App Groups capability to Xcode TargetAttributes, matching
its existing entitlement and the main app's existing capability. Project plist
validation passes. This declares the correct requirement; it cannot replace
Apple portal registration or signed provisioning profiles. Requested account
sign-in after Xcode updates. The app remains uninstalled; the live backend
contract mismatch described above also remains unresolved.

Diagnostics: `/private/tmp/cff-ui-signing-retry.log`,
`/private/tmp/cff-iphone-app-query.log`,
`/private/tmp/cff-xcode-device-support-update.log`, `/private/tmp/cff-ddi-update.log`.

Xcode 27.0 (27A266a) is now installed and its initial setup completed after the
owner accepted Apple's displayed license. Optional simulator downloads were
skipped for this physical-device task. The subsequent app query reached a new
blocker: the phone had locked again; DDI mounting and app inspection are therefore
still not proven. Opened the Apple Accounts sign-in form and requested sign-in
and another phone unlock. Cached CFFB development profiles do not include this
phone; its profile/device registration needs the developer account.

Prepared a separate UI restoration source at `/private/tmp/cff-ui-restoration`
from committed UI revision `9d26658`, leaving all combined working-tree changes
intact. It retains the new charcoal/blue UI, stretched desktop navigation and
positional card headers while using the existing live API contract. Its fresh
production-API build and Capacitor sync succeeded: all 141 packaged web files
match that build. Three Chromium checks against its built output at
`http://127.0.0.1:18450` passed, including desktop/member/admin sidebars and the
390px card theme. Synthetic responses establish UI behavior, not physical push
delivery. This separate package excludes the unreleased combined features;
the canonical combined source and complete unsigned app remain preserved.

Restoration build/test logs: `/private/tmp/cff-ui-restoration-web-build.log`,
`/private/tmp/cff-ui-restoration-sync.log`,
`/private/tmp/cff-ui-restoration-browser.log`,
`/private/tmp/cff-ui-restoration-device-build.log`.

The separate restoration app compiled successfully with Xcode 27.0 for arm64
physical iOS devices with signing disabled. It is 1.0.3 (37), and all 141 compiled
`App.app/public` files match the tested restoration SPA byte for byte. The artifact
is `/private/tmp/cff-ui-restoration-device-build/Build/Products/Debug-iphoneos/App.app`;
it is unsigned and not installable. Final observed Xcode Apple Accounts state
still has `Sign In…` with no account, and the phone lock query reports
`passcodeRequired: true`. Installation and installed-version identification remain
pending account sign-in/profile registration and another phone unlock. No cached
profile was altered to bypass signing or device registration.

## Completed local restoration — October 14, 2026

Confirmed the owner is signed into Xcode's developer account. With the unlocked
phone and Xcode 27 developer image, app inspection succeeded. Xcode 27's app-list
command excludes App Store apps by default; adding `--include-default-apps` to the
scoped bundle query identified the original installation as **CFFB 1.0.2 (36)**,
bundle `org.collegefantasyfootball.app`.

Automatic signing under team `84TV35F6T5` refreshed the development profile and
registered this phone. The final signed restoration package passes strict/deep
code-sign verification and its profile explicitly contains the connected phone.
Installed over the existing app without uninstalling it and launched successfully.
The final device query confirms **1.0.3 (37)**, built by developer. All **141**
packaged UI files match the tested restoration build byte for byte.

Physical Device Hub inspection showed the new charcoal/blue UI and the owner's
existing authenticated homepage. Initial visual verification caught the old Pick 6
promo in the committed restoration snapshot. Applied its existing canonical
removal, rebuilt, re-signed and reinstalled; the final physical view shows matchup
followed directly by roster status with no promo. The full current working tree
was preserved. Three sidebar/player-header Chromium checks and four additional
homepage checks passed; the latter covered guest/authenticated views at 1280px
and 390px with synthetic API responses and no account creation.

This restoration is based on committed UI `9d26658` plus the existing homepage
promo removal, compatible with the currently deployed API. It does not ship the
unreleased combined backend/native features or prove APNs delivery. No production
API, database, worker, App Store or TestFlight release was changed.

Final artifacts: `/private/tmp/cff-ui-restoration/restoration-manifest.json`,
`/private/tmp/cff-ui-restoration-signing.log`,
`/private/tmp/cff-ui-restoration-install.json`,
`/private/tmp/cff-ui-restoration-launch.json`,
`/private/tmp/cff-ui-restoration-installed.json`,
`/private/tmp/cff-ui-restoration-home-browser.log`.
