# Annual membership launch runbook

Source of truth: [2027 membership requirements](../../requirements/29_epic_annual_membership.md).
This branch depends on the unmerged dynasty preview (#425). It must not deploy
membership restrictions or charge users in 2026.

## Configuration and release order

1. Back up the database and apply migrations through `0128_membership_free` in
   staging. `0127_membership` creates the provider ledger and allows deleted
   dynasty managers to leave vacant teams. `0128_membership_free` adds a season's
   two free league choices and backfills existing account rows safely.
2. Configure and certify providers in isolated staging first. Never put secret
   keys in `VITE_*` variables, source control, screenshots or client code.
3. Build web/iOS with `VITE_MEMBERSHIP_ENABLED=true` when the reviewed membership
   screen should be visible. This client flag grants no server entitlement.
4. At the reviewed start of next season, set `CURRENT_SEASON_YEAR=2027`,
   `MEMBERSHIP_ENABLED=true` and an explicitly reviewed, timezone-aware
   `MEMBERSHIP_LAUNCH_AT` in 2027. No kickoff date is invented in the application.
   All three server checks are required. Feature restrictions remain off before
   the timestamp and throughout the 2026 season.
5. Enable `MEMBERSHIP_PURCHASES_ENABLED=true` only after provider certification,
   readiness and the reviewed launch time. Both server rollout switches default
   false. Keep the existing dynasty preview/season integration release gate;
   membership does not make that scoring integration launch-ready.
6. Player portraits still require `PLAYER_HEADSHOTS_ENABLED=true` and a genuine
   source image. Missing portraits retain silhouettes. Keep that availability
   switch false if portraits have not been cleared for release.

If enforcement must be postponed, leave `MEMBERSHIP_ENABLED=false`. Pausing new
purchases uses `MEMBERSHIP_PURCHASES_ENABLED=false`; provider notifications,
existing paid access, cancellation, restore and billing management still work.

## Stripe web setup

- Create one active recurring price: USD 1000 cents, yearly, interval count 1,
  quantity 1. No trial or coupon is offered by Checkout. Configure
  `STRIPE_ANNUAL_PRICE_ID`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` privately.
- Use test keys only outside production. Production readiness refuses test keys.
- Set `PUBLIC_WEB_URL` to the canonical HTTPS website. Checkout success/cancel and
  portal return URLs are server-owned. Enable the Stripe Customer Portal with
  cancellation/management for the same product.
- Register `POST /membership/webhooks/stripe` on the API host. Preserve the raw
  request body and `Stripe-Signature` through the proxy. The backend SDK pins
  Stripe API **2024-06-20**; use that version for the webhook endpoint too.
- Subscribe to `checkout.session.completed`, `customer.subscription.*`,
  `invoice.paid`, `invoice.payment_failed`, `charge.refunded`,
  `charge.dispute.created`, and `charge.dispute.closed`. Re-fetching current
  provider state prevents old notifications from resurrecting refunded access.
- Verify initial paid checkout, abandoned checkout, two browser tabs, lost webhook
  then reconciliation, renewal, failed renewal, paid-through cancellation,
  immediate cancellation, full refund, disputes, duplicates, reordered delivery,
  provider outage, portal and account deletion. Check the actual provider ledger.
- A full refund or unresolved dispute revokes that paid period; partial refunds
  do not revoke it. An older period's refund cannot erase a newer paid period.
- Rotate price/product identifiers only with a reviewed migration of historic
  subscriptions; this implementation intentionally accepts one configured SKU.

## App Store setup

- Create an auto-renewing **one-year** subscription with US price $10 and no
  introductory free trial, family sharing or promotional price. Confirm App Store
  Connect supports the intended price point before launch; the app displays the
  actual localized `Product.displayPrice` before purchase.
- Set `APPSTORE_PRODUCT_ID`, `APPSTORE_BUNDLE_ID`, numeric `APPSTORE_APP_ID` and
  `APPSTORE_ENVIRONMENT=Production`. Sandbox is isolated staging only and is
  refused by production readiness. Real annual periods must last at least 350
  days; accelerated sandbox renewals are permitted in staging.
- Configure App Store Server Notifications V2 to
  `POST /membership/webhooks/apple`, including a separate sandbox endpoint.
  The official Apple SDK verifies outer and nested signed payloads, product,
  bundle, environment and trusted roots. Permit its outbound revocation checks.
- Membership status supplies a server-generated account UUID. StoreKit purchases
  use `appAccountToken`; receipts restore only to the original CFFB account.
  Changing a client-supplied user/customer ID cannot transfer ownership.
- Ship the native `ProMembership` plugin with the new app build. Older native
  builds never fall back to a web purchase. Native transactions finish only after
  the API acknowledges verification; failed/offline receipts remain unfinished.
- Certify actual Sandbox/TestFlight purchase, pending/Ask to Buy, cancellation,
  restore after reinstall, account switching, renewal, billing failure, expired
  entitlement, refund/revocation and server-notification retries. Simulator build
  and mocked boundary tests alone cannot certify actual payment processing.
- App Store renewal is managed by Apple. Deleting a CFFB account does not cancel
  Apple billing; Settings and Membership expose management and explain this.
  Web account deletion cancels owned Stripe subscriptions before data removal.

## Entitlements and support

- The first promised early-access Pro year begins at launch (or redemption, if
  later) and lasts one calendar year. It needs no card and does not auto-renew.
- Provider periods are authoritative. A URL query, client cache or signed-out
  browser cannot create a paid grant. Multiple valid grants use the latest end.
- Free users can create/join two regular leagues each season. After expiry,
  the oldest two remain manageable by default; the manager may fix another pair
  once that season in Membership. Other leagues stay readable. Active free
  selections cannot rotate to bypass the limit; removed/archived selections can
  be replaced. Dynasty participation always requires Pro after rollout.
- Manual roster/draft/waiver/trade actions enforce the selected free leagues.
  Automated scoring, scheduled picks and waiver processing continue so retained
  history is coherent for all other league members.
- All weekly entry edits/submissions and duel acceptances require Pro; existing
  results and entries stay readable, and declining an invite remains available.
- Live matchup viewer refresh is 15 seconds for Pro and 180 for free. The
  upstream provider's shared polling/freshness timestamps remain authoritative;
  this does not sell a faster upstream feed.
- The membership API returns private, non-cacheable personalized responses.
  Audit rows retain provider event/subscription identifiers after account deletion
  with `user_id=NULL`; they cannot be rebound to a new account. No cards, raw
  signed receipts or authorization headers are persisted in the membership ledger.

## Validation and rollback

Run backend/API and web tests, type checks, production web build, PostgreSQL
upgrade/downgrade/drift and the iOS simulator build. Bruno membership requests
cover status, server reconciliation, checkout, portal, receipt verification and
free league selection; use a disposable environment for provider tests.

Prefer disabling the rollout to rolling back schema. Downgrading 0127 after a
dynasty manager has been deleted deliberately fails: the earlier non-null
ownership schema cannot recreate deleted identities. Restore a reviewed backup
or keep the nullable schema. Downgrading also discards billing audit data, so
retain that data before any destructive schema rollback.

References: [Stripe webhooks](https://docs.stripe.com/webhooks),
[subscription notifications](https://docs.stripe.com/billing/subscriptions/webhooks),
[Apple server library](https://github.com/apple/app-store-server-library-python),
[StoreKit](https://developer.apple.com/documentation/storekit/implementing-a-store-in-your-app-using-the-storekit-api),
[Apple public roots](https://www.apple.com/certificateauthority/).
