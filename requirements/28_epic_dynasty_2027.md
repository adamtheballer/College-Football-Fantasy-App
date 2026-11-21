# Epic: 2027 Dynasty Preview

## Summary

Build a separate, disabled-by-default 2027 dynasty preview. Do not merge or deploy
this work into the 2026 release. Existing redraft, scoring, player values, drafts,
trade workers and normal league-creation UI remain unchanged.

Dynasty leagues, franchises and rosters use separate tables. Only account and
player identities are shared; no regular League, Team, Draft or RosterEntry is
created. Existing workers and normal league endpoints cannot operate on them.

Managers retain the full roster between seasons. The startup draft includes all
reviewed eligible college players in randomized snake order. Each subsequent
offseason has a snake draft containing only reviewed incoming freshmen. There is
no recruiting-class-rights mode. Future draft picks are transferable assets.

## Decisions and configuration

- Non-playoff teams draft first, lowest regular-season winning percentage first.
- Playoff teams follow in reverse playoff finish; champion last. If everyone
  qualifies, reverse playoff finish determines the entire order.
- Ties use lower regular-season winning percentage, then lower points scored,
  then stable franchise ID. These explicit preview tie-breakers are reviewable.
- Rosters, startup rounds, freshman rounds and future-pick horizon are configured
  at creation; no conversion or mode-change endpoint is provided.
- Transfers retain fantasy ownership. Missing eligibility data never causes a
  player to disappear. Only a reviewed season-specific departure can remove a
  player at rollover, with the prior roster retained in the season snapshot.
- Freshman eligibility means first college-entry season, not merely a displayed
  Freshman/redshirt label. Current 2026 bios are not a 2027 recruiting dataset.
- Dynasty value is a separate, versioned preview estimate incorporating reviewed
  class and optional verified age. It never overwrites redraft/CFB27 values.

## Implementation stories

1. **Persistence and isolation:** additive future-only league/season/franchise,
   catalog, pick and trade records; disabled feature gate; production 2026 deny.
2. **Draft and rollover:** startup shuffle, durable snake turns, freshman-only
   annual pool, retained rosters, immutable close-season results, draft order.
3. **Assets and value:** future picks retain originating franchise identity after
   trades; both parties consent; atomic, ownership-checked, retry-safe settlement;
   player/pick package support; separate age/class value breakdown.
4. **React preview and contracts:** authenticated, unlisted `/labs/dynasty` page,
   typed API, creation/join, shared draft room/rosters/picks/trades/season controls; gated
   in both browser and server; Bruno and browser verification.

Each story must have a matching GitHub issue referencing this file.

Published tracking: [epic #420](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/420),
[persistence #421](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/421),
[drafts #422](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/422),
[assets #423](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/423),
[React #424](https://github.com/adamtheballer/College-Football-Fantasy-App/issues/424).

## API specs

All routes are under `/dynasty`, use existing bearer authentication and league
membership/commissioner/ownership guards, and return stable `detail` errors.
Disabled mode returns 404. Production with current season before 2027 returns
404 even if the flag is mistakenly enabled. Creation rejects seasons before 2027.

- `POST /leagues`: create a new preview league; no existing-league conversion.
- `POST /join`: join an unstarted league using its invite code.
- `GET /leagues`, `GET /leagues/{id}`: member-only list/state, bounded collections.
- `GET /capabilities`: authenticated server preview gate.
- `GET /leagues/{id}/history/{season}`: closed results and roster snapshot.
- `POST /catalog`: administrator-only reviewed season facts with source URLs.
- `GET /leagues/{id}/pool`: paginated eligible players and separate dynasty value.
  `available_only=false` supplies the complete locked draft board, including
  selected players, with stable `draft_rank` values; no returning players are
  added to annual freshman drafts. State includes current draft selection
  history, server time and configured team count for the shared draft screen.
- `POST /leagues/{id}/start`: commissioner locks a complete league's draft order.
- `POST /leagues/{id}/picks/{pick_id}`: current asset owner selects a player.
- `POST /leagues/{id}/rosters/{entry_id}/drop`: owner makes roster space; dropped
  players cannot be selected twice in the same draft.
- `POST /leagues/{id}/trades`, `/trades/{trade_id}/accept`, `/cancel`, `/reject`:
  propose and settle scoped player/pick packages.
- `POST /leagues/{id}/close`: commissioner submits complete reviewed season
  results; frozen rosters/results are preserved. Preview uses explicit review;
  automated scoring/postseason integration is a later launch gate.
- `POST /leagues/{id}/rollover`: next year only, after closure; retained rosters,
  reviewed departures, annual incoming-freshman pool and next future-pick assets.

Mutations lock the dynasty league record before checking state/ownership. Unique
constraints prevent duplicate pick assets and duplicate drafted/rostered players.
Stale trades fail without transferring any asset. Pick numbering follows the
originating franchise's standings position, independent of its current owner.

## UI specs

React `web/` is canonical. No Streamlit work. The preview route requires an
explicit frontend flag and the server capability gate, has no normal navigation
entry, and is absent from normal 2026 league creation. Show loading, denied,
empty, error, retry, draft-turn and roster-capacity states honestly.

**User correction: preserve the normal draft UI.** Both startup and annual
drafts render the existing `web/client/pages/Draft.tsx` at the gated
`/labs/dynasty/{leagueId}/draft` route. Keep its layout, styling, board, search,
queue, roster/history tabs and pick confirmation. Adapt the dynasty data and
actions underneath it; do not create a second player table or redesign the
draft room. Annual drafts change the player pool to reviewed incoming freshmen.
The management dashboard links to this room and has no separate pick controls.
Preview picks remain untimed; show a dash in the existing timer slot and retain
normal timer-expiry behavior for regular drafts.

## Acceptance criteria

- Default deployment cannot use dynasty routes or expose a creation option.
- Dynasty draft layout is the canonical normal draft screen; the dashboard has
  no alternate drafting table. Startup keeps the full eligible pool; annual
  drafts contain only incoming freshmen. Normal drafts retain existing behavior.
- A 2026 league cannot be created or converted through dynasty endpoints.
- Startup randomness is materialized once; reopening/retrying cannot reroll it.
- Round two reverses round one. A traded pick selects for its current owner.
- Annual freshmen exclude returning/redshirt freshmen and already-rostered players.
- Rollover never clears retained rosters or guesses graduation from class alone.
- Non-members cannot read or mutate; only owners pick/offer; recipients accept;
  commissioner-only start/closure/rollover; administrators review catalog facts.
- Duplicate picks, full rosters, stale/cross-league assets and concurrent attempts
  are rejected atomically. Accepted-trade retries do not replay transfers.
- SQLite behavioral tests and disposable PostgreSQL migration/concurrency checks
  pass; React types/tests and a browser workflow pass; no production migration.

## Launch gates

This is a reviewable preview implementation, not a 2027 release authorization.
Before launch: import/review the real 2027 player and freshman datasets, finalize
valuation weights and league configuration defaults, integrate season results
with authoritative postseason/scoring, and approve a separate 2027 rollout.
