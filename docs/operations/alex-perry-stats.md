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
