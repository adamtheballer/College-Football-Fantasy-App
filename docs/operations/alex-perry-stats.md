# Alex Perry stats correction — verified locally, release held

Current catalog identity: player **1082**, Alex Perry, Illinois, WR.
Trusted ESPN athlete ID: **5084133**. His 2025 team was FIU. Illinois' official
2026 biography confirms 13 starts, 56 catches, 840 receiving yards and nine TD:
https://fightingillini.com/sports/football/roster/alex-perry/15841

The reported game lines are 2025 FIU records, not 2026 Illinois records. The
previous ingestion did not persist per-game historical facts. The frontend also
hid historical game rows behind a 2026-only condition; default season selection
preferred a newer team schedule even when it contained no player stats.

The correction persists season/event-keyed historical game facts with source
metadata and historical team identity, separately from live fantasy scoring.
It renders the selected historical season and defaults to the newest recorded
player games when a newer schedule contains no player production. Explicit
2026 selection still returns the 2026 schedule and missing-stats state. It does
not copy 2025 production into 2026 or fabricate zero/DNP records.

Alex's verified 2025 log contains 13 games including the bowl, with 56 REC,
840 receiving yards and nine receiving TD. Screenshot examples checked exactly:

| Opponent | REC | Receiving yards | Receiving TD |
| --- | ---: | ---: | ---: |
| Middle Tennessee | 5 | 71 | 2 |
| Liberty | 8 | 88 | 1 |
| Jacksonville State | 4 | 109 | 1 |
| Sam Houston | 7 | 140 | 2 |
| UTSA | 3 | 24 | 0 |

The summary distinguishes games with recorded stats from authoritative total
participation. Official season totals remain preferred when imported; derived
per-game totals are retrieval-only fallbacks.

Latest verification (October 14, 2026): **22 backend game-history/game-log tests
passed**, including explicit/default season selection, all five screenshot lines,
transfer identity, malformed/future data, source corrections, duplicate-event
merging and preservation of live scores. **Two Chromium checks passed**, at
1280px and 390px, against actual public player/card/game-log APIs on the isolated
local replay database. Only the shell session is simulated; no account login,
password or player-stat response interception is used. They verify the default
2025 selector, FIU context, season totals, five game lines, all 13 records, no
page overflow and the existing full-height desktop sidebar. This is browser
verification, not a signed physical-iPhone test.

No push, merge, deploy, production migration/backfill, native app build or Store
release was performed. Migration 0120 and its source import remain prepared for
the combined release. The installed app/live site will not change until that
release is explicitly authorized.

Other issues remain queued at the owner's request. The broader source review
still has seven identity gaps and an unfinished kicker-role fallback validation;
its existing partial test results are not reported as full completion. Do not
mark the complete player catalog, push/APNs, installed-phone UI or charts done
based on the Alex Perry checks.

## Production follow-up — October 17, 2026

The combined release deployed the reader but omitted the per-game history
import: production contained zero `player_historical_game_stats` rows. A legacy
2026 Week 1 `backfill_zero_stat` row contained only event/player metadata. The
reader calculated 0 points for it, which prevented the default-season fallback
from selecting recorded 2025 production even after an import.

The follow-up rejects metadata-only backfill placeholders at the game-log read
boundary, falls through to accepted game/weekly facts, and preserves explicit
recorded zero counts. Explicit season requests remain honored. The read path
does not change source rows, league points or historical season identities.

Production import used the existing strict `store_player_game_history` service
and trusted ESPN identity 5084133. All 13 source events were validated before
commit, including the five reported lines and totals of 56 receptions, 840
receiving yards and 9 touchdowns. The prior table state for this player/season
was empty. An immediate second import reported 13 unchanged rows; Alex's live
`PlayerGameStat` records were unchanged. An import-run audit records the repair.
ESPN returned no 2026 per-game production; 2025 facts must not be relabeled 2026.

The live weekly waiver audit covered Weeks 0–7 and every position for Week 4.
Week 4 returned 704 scored available players out of 763, sorted before
pagination; leaders were Wayshawn Parker (46.9), Mason Heintschel (43.42) and
Keelon Russell (40.1). The reported screenshot was taken before the weekly-sort
API deployment. The native client already refetches this query on mount, focus
and every 30 seconds. These server checks do not claim that every absent score
is a verified zero or that the old screenshot proves the current phone state.
