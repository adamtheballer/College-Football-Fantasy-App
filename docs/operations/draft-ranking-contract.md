# Draft ordering — local New Build correction

The default remains the established positional-value master board, now computed
once by `api/app/services/draft_rankings.py`. It is not raw projected-points sorting.
Both React boards consume its versioned ranks; ranking-based server auto-pick and
backend mock auto-pick use the same full context. The active mock experience uses
`singlePlayerMockDraft.ts`; the backend mock routes remain intentionally inactive.

## Confirmed defects and example

Previously React recomputed ranks separately from server sorting/auto-pick. The
real position filter additionally replaced the default with points ordering.
Missing source ranks could still receive high computed ranks. ROS/positional
ranks were used as substitute overall rank inputs, and a source/estimated position
could be labeled ADP. Page-limited server selection and fetching only partial
catalogs could hide candidates. The seasonal fallback spread a twelve-game total
across thirteen calendar weeks. Missing forecast inputs became zero.

Current Trent Mosley is **1881, USC, WR**; the retained historical ID 251 is a
separate record. The captured public source has 245.5 season points, no overall
CFB27/source rank and no observed ADP. An exact legacy replay placed him at 27;
the reported live top-20 position is not independently confirmed. The corrected
815-player source replay places him at 813, after 811 valid ranked players and
Jamal Rule. The actual isolated API has one extra test player and places him at
814, retaining 245.5 points. This is the global missing-rank rule, not a Trent
exception. The card's WR119 label represents cumulative finalized current-season
**positional fantasy rank**, not overall draft rank, source rank or observed ADP.
The screenshot alone does not establish his current value in that metric.

## Exact policy and ordering

The existing final score retains **60% fantasy value, 20% market component,
12% CFB27 talent, 8% role certainty**, minus existing risk penalties. Fantasy
value is 65% positional scarcity percentile and 35% projected-points percentile.
The market component is 60% computed TPR-rank percentile and 40% source-rank
percentile. TPR retains 55% projection z-score, 15% scarcity z-score, 10% role,
10% historical z-score, 5% play environment and 5% consistency, plus the prior
position multipliers and penalties. The existing QB-depth guard, kicker floor,
position adjustments, within-position points ordering, one-final-game protection,
and established KJ Duff/Nick Marsh editorial moves are preserved. No new player
exception or arbitrary weight was introduced. The golden 815-player replay checks
all previous talent values and weighted scores to 0.001 with the original config.

After those rules, valid source-ranked players come first. Unranked players follow
by known projection descending, normalized name, then unique ID; missing forecasts
follow real zero. Source input is valid observed sheet ADP, otherwise the seeded
CFB27 rank. ROS rank and positional rank never substitute for that source rank.

- **Overall draft rank:** master rank ascending, unique ID tie-break.
- **Source ADP:** observed positive finite sheet ADP ascending; absent/invalid last,
  unique ID tie-break. No CFB27/computed/estimated ADP is displayed as observed ADP.
- **Season / remaining points:** valid forecast descending, unknown last, unique
  ID tie-break. Full source season before verified games when weekly data is absent;
  remaining published/fallback weeks after certified games. Published snapshots
  remain authoritative; the prior bounded form adjustment is retained.
- Existing school/position/name API sorts keep their meanings and ID tie-breaks.

League scoring and conferences are authoritative; real and mock rank identically
with matching pool/settings. Fixed roster demand includes FLEX1 plus BENCH5,
represented as BE6 by the existing replacement-value algorithm. Search/position,
drafted/unavailable and roster legality filters preserve master ranks. Global sort
runs before pagination; filtered row number never replaces overall rank.

## Refresh and selection safety

The bounded pure-value cache is keyed by all ranking inputs, config and ratings
content revision. Data changes produce a new fingerprint; ORM objects and draft
availability are not cached. Every page carries season, current week and version.
The client rejects mixed versions/periods/totals, invalid row ranks, duplicate IDs
and truncated full-pool fetches. Query keys include league, season, sort and config;
requests use AbortSignal. Supplemental projections use the authoritative API week
instead of default Week 1. Foreground boards refresh every 60 seconds and on focus;
own picks invalidate the pool. Failed refresh retains the last loaded board.
React Query structural sharing prevents arbitrary rerender ordering changes.

Rows, selected cards and picks use stable IDs. Deliberate queues keep their order.
Mock timeout auto-pick retains queue precedence, then existing starter/roster AI
rules over the corrected board. Real queues remain the existing visit-local
research queue; server timeout picks use league rankings and legality. No completed
pick, ownership, roster identity or league history is changed by ranking refresh.

## Full-pool audit and verification

See `draft-ranking-audit-2026-10-13.json`: **815 eligible, 811 valid source-ranked,
4 unranked; 0 observed ADP; 815 finite season projections; 0 duplicate IDs or
name/school/position identities.** Positions: QB135/RB204/WR273/TE136/K67. All
projection markers are 2026. Source sync dates span August 10–September 12; the
captured public response has no ROS snapshots. Unranked: Jamal Rule, Trent Mosley,
Javian Mallory, Legend Bey. Their missing authoritative rank/ADP is a source gap,
not permission to invent data. Live current-season completeness is not certified.

Verification: SQLite draft/ranking/room/mock/positional-card checks **113 passed**; focused
ranking regression **21 passed**; PostgreSQL ranking contract **21 passed**
after correcting teardown order; React **590 tests,
94 files passed**; app/test/Vite TypeScript checks passed. Full unauthenticated
local API pagination: **816 rows, unique IDs, continuous master ranks, one version,
Week 7**, with 815 captured catalog players plus one local fixture. Browser
Chromium at localhost18448: **8 passed**, including 1440px/390px real/mock numeric
sorts, zero points, stable filtered ranks/search, queue preservation, open-card
identity during refresh, the resulting draft ID, expiry, confirmed pick animation,
reconnection/conflicts, completion and mobile centering. Browser draft checks use
isolated response fixtures; they are not a signed iPhone test. Screenshot evidence
is retained in `web/test-results/draft-reliability-*`.

No ranking migration is needed: the correction is read-only at runtime and changes
no stored ranks/picks. Existing combined-release migrations remain held locally.
No push, merge, deployment, production migration, native sync/installation,
TestFlight upload or Store release is authorized or performed.
