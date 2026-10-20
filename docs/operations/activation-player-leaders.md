# Positional leaders and participation

Scope: `requirements/activation-and-player-leaders.md` (issues #405–#412).

## Player results

`GET /player-rankings/leaders` feeds Home, immediately below Weekly Challenges.
`GET /player-rankings` feeds the searchable, paginated player table. Both use
exact-game verified final box scores and the same scoring helper as player
charts. Latest completed week is the default; season totals are explicit.
Raw points are not projections. Missing/ambiguous facts remain Pending; only a
verified zero is zero. Missing raw stat columns show a dash, including legacy
FPTS-only facts; season columns require that stat in each counted game. A bye requires a canonical schedule bye. Week 0 is mapped
to fantasy Week 1 once; Week 15 becomes available after its final rollover.

League requests require current membership and use the league scoring snapshot
and conference pool. `mine=true` filters the caller's roster **after** positional
ranks are calculated across the eligible pool. Legacy players outside that pool
remain visible with no eligible rank. Player pictures obey the existing server
switch, with an initials fallback when disabled or unavailable.

## Home and first participation

Home highlights a saved incomplete entry or a simple open challenge, preferring
Lock of the Week. Deadline state uses the existing server-anchored clock; the
backend remains authoritative. Home reminders cover the caller's injured
starters, canonical kickoffs within 24 hours and incoming proposed trades.
A failed query offers Retry and is not shown as an empty healthy dashboard.

The welcome guide has three skippable steps and can be replayed from Settings.
Accounts created after 1.0.3's release skip the historical ten-step update recap.
Existing receipts remain consumed. Native automatic reviews require a submitted
challenge or a final matchup involving the account's team. The existing atomic
once-only claim still applies. `review_request_invoked_at` records only an
explicit `invoked:true` bridge result; neither receipt proves a displayed sheet,
a rating, or an App Store review. Browser sessions cannot claim or acknowledge.

## Health and metrics

Admin UI: `/admin/participation`, linked from Weekly Challenges administration.
Admin APIs: `/product/admin/participation?days=7` and
`/product/admin/player-health`. Use `include_test_accounts=true` explicitly to
include otherwise excluded admin/test accounts. The migration marks only the
previously confirmed automation username as a test account; no email/name
heuristic labels other users.

Participation is a rolling 1–90 day window. New-account counts and new accounts
in leagues form a separate signup cohort; active/returning/view/start/share
counts are observed optional events, not all installed users. Official entrants
and submissions come from ChallengeEntry. Native versions are versions observed
in instrumented sessions, not proof that every installation updated.

`POST /product/events` uses the authenticated account plus an account precondition.
Events are daily deduplicated and capped at 100 per account/day. No arbitrary
properties, emails, content, tokens, or full URLs are accepted. Reuse the account's
existing analytics preference, exposed in Settings and Challenges; Do Not Track
is respected. Raw usage and challenge analytics expire after 90 days. Functional
entries, scores, authentication and once-only review receipts are unaffected.

The existing lifecycle worker runs the health/retention task at most hourly,
with an atomic persisted due claim. It runs after critical lifecycle commits in
a separate transaction. Failed checks persist a failed receipt and back off;
they cannot roll back a draft, waiver or trade. Inspect ProviderSyncState with
provider `cffb`, feed `product_health`, scope `season:<year>` and worker logs.

Read-only command: `PYTHONPATH=. uv run python scripts/check_player_data_health.py
--season 2026`. Exit 2 means evidenced source gaps, invalid inputs or a stale/
unknown reviewed injury feed. An absent box-score row alone never establishes
participation or a zero. Each official conference source is checked separately using its persisted
fetch receipt, so a no-change refresh still counts and one failed conference
cannot be hidden by another. A source not successfully checked for 48 hours is
stale in season; this reports freshness and never bulk marks players healthy.

## Rollout

Migration 0126 is additive and must precede the new frontend. Older clients can
ignore the extra review-state fields and receive `not_eligible` without consuming
a claim. Existing app versions will not send new usage events. A new bundled
frontend is needed to show the new Home/table/guide in the installed iOS app;
this change does not sync Capacitor, increment a build, or submit to Apple.
