# Player Popularity and Daily Hot Pickups

## Story 1 — Rostered and Start percentages

For each canonical player in the active 2026 season, expose separate `Rostered`
and `Start` percentages for the current fantasy week. The denominator is the
set of completed, current-season custom leagues in an active post-draft state;
mock drafts use a separate data model and are therefore excluded. Count each
league once. Rostered includes active, bench, and IR membership; Start uses the
persisted kickoff-frozen lineup snapshot and counts only scoring slots,
including FLEX. A player without any frozen kickoff snapshot renders Start as
unavailable, never `0%`. The current schema has no demo/test/void marker, so
this release deliberately does not invent unsafe name-based exclusions; a
future explicit flag is required before such leagues can be excluded.

The API returns server-side values, status, season/week and computed timestamp
in one batched response. The Roster and league Waiver views use a shared compact
presentation below player game information. Derived metrics are reconciled and
published once daily by the existing lifecycle worker; they must not change
roster, scoring, lock, trade, or waiver behavior.

## Story 2 — Daily Hot Pickups

The league Waiver view offers `All Players | Waiver Wire | Hot Pickups`.
Hot Pickups has a daily atomic snapshot for `last_7_days` (default) and
`last_24_hours`, with a configurable/default 06:00 UTC cutoff. It ranks distinct
eligible leagues per player for committed free-agent additions and successful
waiver awards only. It excludes draft, trade, pending, failed, cancelled,
administrative, mock/test/demo, and duplicate same-league pickups.

The league-scoped read applies current league availability before pagination and
keeps the existing Add/Claim authorization as the final authority. It returns
snapshot cutoff/freshness/coverage metadata, never exposes cross-league private
data, preserves the last successful snapshot on refresh failure, and does not
let customer requests trigger recomputation.

## Acceptance and verification

Implement database migrations, lifecycle-worker reconciliation, FastAPI
contracts, React hooks/UI, accessibility, and isolated tests for cohort rules,
lineup history, slot types, pickup qualification/deduplication, daily snapshot
idempotency, stale availability, loading/error/empty states, mobile layout, and
a real API/database workflow.
