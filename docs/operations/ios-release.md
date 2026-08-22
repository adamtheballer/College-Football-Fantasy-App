# iOS App Store release

The iOS app packages the canonical React/Vite output from `web/`; it does not
load the hosted website in a WebView. The bundle uses the production API
directly, while the website continues to use its same-origin Vercel `/api`
rewrite.

## Local build

Install full Xcode (not only Command Line Tools), then run:

```bash
cd web
npm ci
npm run ios:sync
npm run ios:open
```

The iOS bundle identifier is `org.collegefantasyfootball.app`. Do not register
or change that App ID after creating its App Store Connect record without an
explicit product decision: a published bundle identifier is permanent.

## Required one-time Apple and provider setup

1. In Apple Developer, register `org.collegefantasyfootball.app` under the
   correct team and enable **Push Notifications**.
2. Open `web/ios/App/App.xcworkspace` in Xcode, select the App target, choose
   the Apple signing team, and add **Push Notifications** plus **Background
   Modes → Remote notifications**.
3. Add the Apple APNs `.p8` key, key ID, and Apple team ID to the existing
   OneSignal app’s iOS platform configuration. The web and native app may use
   the same OneSignal App ID, but iOS delivery will not work until APNs is set.
4. Replace the generated Capacitor placeholder icon with final 1024×1024 App
   Store artwork. Keep the image square, opaque, and without rounded corners;
   iOS applies its own mask.
5. In Railway, include this exact value alongside the public web origins in
   `CORS_ORIGINS`:

   ```text
   capacitor://localhost
   ```

   Do not use a wildcard or a `localhost` HTTP origin in production.

## Release verification

On a physical TestFlight device, verify signup/login, token refresh after the
access-token lifetime, profile-photo selection, deep links, notifications,
injury-alert league selection, live matchup refresh, and logout/login identity
handoff. A simulator build is useful for UI verification but cannot certify
APNs delivery.
