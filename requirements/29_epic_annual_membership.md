# Epic: 2027 Annual Pro Membership

## Summary

Add a $10 USD/year Pro subscription on web and iPhone, launching at the start
of the 2027 season. Free managers may participate in two leagues; Pro managers
may participate in unlimited leagues, use dynasty, see available player pictures,
get more frequent live-scoring refreshes and enter weekly challenges.

This branch builds on the unmerged dynasty preview. No 2026 release, production
migration, charge or access restriction is authorized by this implementation.
Both a disabled-by-default rollout setting and a configured 2027-or-later launch
timestamp are required. Never choose a season kickoff date without reviewed data.

## Confirmed behavior

- Price: $10 USD per year; one account's verified Pro access works on both platforms.
- Free limit is two regular league memberships per season, counting created and
  joined leagues. Dynasty participation separately requires Pro. After expiration,
  existing memberships and history survive; two regular leagues remain manageable
  and additional leagues are read-only. The oldest two are the default; a free
  manager may choose a different pair once per season. Active selections cannot
  be rotated to bypass the limit. A third enrollment requires Pro.
- Pro is required for dynasty participation and weekly-challenge entry/edit/submit
  actions. Public browsing, rules, results, existing entries and league history
  remain readable; rejecting an invitation never requires payment.
- Existing early-access code recipients receive the previously promised Pro
  year from launch (or redemption, if later), once, without a card or charge.
- Pictures remain subject to actual source availability. Free API responses must
  not contain player picture URLs when membership enforcement is active.
- Pro live-scoring refresh checks available data every 15 seconds versus the
  existing three-minute standard cadence. Provider polling remains shared and
  unchanged; do not promise or fabricate a 15-second upstream scoring feed.
- Cancellation stops renewal; access remains through verified paid-through time.
  Expiry/refund/revocation removes paid capabilities without deleting rosters,
  past challenge entries or purchased-history audit records.
- Web uses Stripe Checkout and billing portal. iPhone uses StoreKit 2 purchase,
  restore and subscription management. No web checkout is substituted for native
  digital purchases. Apple supplies localized product prices.

## Implementation stories

1. **Entitlements and persistence:** account/provider identifiers, verified
   subscription periods, idempotent event receipts, feature policy, launch gates,
   early-access grants and enrollment concurrency.
2. **Verified billing:** Stripe checkout/portal/reconciliation and signed webhooks;
   Apple signed transaction/notification verification and immutable account binding;
   cancellation, expiration, refund, replay and provider-failure handling.
3. **Feature enforcement:** league enrollment, dynasty mutations, all weekly
   challenge participation paths, API picture stripping and live-refresh policy.
4. **Web and iPhone UX:** one membership status contract, price/features page,
   upgrade/manage/restore states, native StoreKit bridge, contextual feature gates,
   tests, Bruno workflows and launch documentation.

Publish the epic and each story as GitHub issues referencing this file.

Tracking: [epic #426](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/426),
[entitlements #427](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/427),
[billing #428](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/428),
[enforcement #429](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/429),
[UX/certification #430](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/430).

## API and trust boundaries

- `GET /membership`: authenticated plan, provider readiness, launch state,
  verified expiry, feature capabilities, league usage/limit and Apple account token.
- `POST /membership/checkout`: server-owned annual Stripe price, own customer,
  reusable unexpired checkout session. No client price, customer or user IDs.
- `POST /membership/portal`: own Stripe customer management URL.
- `POST /membership/sync`: reconcile the authenticated customer's Stripe state.
- `POST /membership/free-leagues`: select up to two owned regular leagues for
  the season; preserve active free selections after the first choice.
- `POST /membership/apple/verify`: verify a signed transaction with Apple's SDK,
  trusted Apple roots, configured bundle/product/environment and account token.
- `POST /membership/webhooks/stripe`: verify raw body signature; fetch current
  provider authority, deduplicate events, serialize updates per account.
- `POST /membership/webhooks/apple`: verify notification and nested signed
  transaction/renewal payloads; reject stale/replayed or wrong-account grants.

No client flag, checkout redirect, unsigned JSON, unverified receipt, expired
period, sandbox transaction in production or arbitrary metadata can grant Pro.
Do not retain payment cards, raw authorization headers or private signing keys.
Expose actionable errors and fail closed on unverified purchases. Provider outages
must not remove an existing still-paid entitlement or produce a fake success.

## UI and rollout

React `web/` is canonical; preserve the existing draft UI. Add a membership page
and contextual upgrade notices. Show the store's actual native price before a
purchase; cancellation/pending/offline/restore failures never show paid success.
Finish native transactions only after the server acknowledges verified ownership.

Before launch, configure real Stripe products/keys/webhooks and App Store product,
bundle/app identifiers and notifications; run actual Stripe test mode and Apple
sandbox/TestFlight purchase/renewal/refund/restore tests in isolated environments.
Set an explicitly reviewed 2027 launch timestamp. Live payment configuration,
publishing an iPhone build, merge and production rollout are separate launch work.

## Acceptance

- Defaults and all 2026 requests preserve current behavior; no premature charges.
- Pro purchase/renewal works across platforms, with restoration and no double grant.
- Webhooks are authenticated, idempotent, safe out of order and bound to one account.
- Unpaid concurrent third league enrollments cannot exceed two slots.
- All participation APIs reject unpaid users after launch; reads/history survive expiry.
- Missing player images/projections remain honest; no rating/scoring fabrication.
- Tests cover billing security, expiration/cancellation, league races and UI failure
  states; PostgreSQL migration upgrade/downgrade/drift and browser checks pass.
