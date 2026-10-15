# Matchup applied-record highlights — combined release held

Implemented locally October 14. Keep this work with the combined new build. No
production migration, deployment, push, merge, TestFlight/App Store upload or full
combined app installation occurred.

## Root cause and authoritative flow

The Matchup response previously exposed a finalized status and an independently
selected standing record, without proof that this exact result had reached those
records. Comparing scores or checking a generic timestamp would color pending or
stale counts. Aggregate counts alone also cannot distinguish corrections that
offset one another.

`api/app/domain/matchup_records.py` shares the existing finalized-results
calculation with the scorer and read-side verifier. Both existing standings writers
(`scoring_service.recalculate_standings_for_week` and the legacy weekly scoring
script) stamp an exact result/record fingerprint in the same transaction as the
standing rows. The fingerprint includes league, season, week, matchup, both team
IDs, finalized status/scores and both cumulative W-L-T/score totals. Existing
scoring, record accumulation and postseason cutoff rules remain unchanged.

Migration `0122_matchup_record_application` adds one nullable receipt column.
Legacy rows receive no invented proof; they stay neutral until the existing scorer
recalculates their exact results. Downgrade removes only the receipt column.

The Matchup read verifies the exact receipt and both persisted standing rows
against the same finalized results. It returns each updated record together with
`record_highlight=win|loss|null`. Pending application, inconsistent records,
corrections not yet applied, ties, byes and postseason records remain neutral.
This read does not write records or increment anything. Both teams must pass
verification, irrespective of the viewer's team.

## Existing weekly lifecycle and frontend scope

Eligibility uses `resolve_matchup_display_week`, which already retains the
completed matchup through Tuesday even after the operational weekly reset.
`next_matchup_display_rollover_at` derives the existing Wednesday 00:00 Eastern
display boundary and confirms that the existing resolver advances there. It does
not change rollover policy or add a midnight/24-hour rule. Season-end or fallback
schedules that do not advance receive no fabricated deadline.

The response includes `current_matchup_week` and `matchup_week_rollover_at`.
`web/client/components/league/MatchupRecord.tsx` validates league, season, current
week, finalized status, deadline and count before rendering the whole winning
count green or losing count red. Other numbers/hyphens inherit existing styling.
The fragment preserves the existing inline record text and layout, and is used
only on the Matchup page. No banners, badges, animations or local persistence.

`useLeagueMatchupTab` keys cache by season and requested context, passes the abort
signal and rejects mismatched league/season/week/matchup replies. Finalized pages
continue polling and refetch on mount/foreground. The page clears expired colors
at the server-derived boundary and refetches; the existing native foreground
listener bridges React Query focus. Historical navigation and late replies cannot
restore an expired highlight. Applied corrections receive a new receipt and update
record/color together; repeated scorer runs do not increment or extend eligibility.

## Verification actually run

- Backend SQLite: 123 passed, one skipped across record, scoring, postseason and
  native-push/provider/event checks.
- PostgreSQL: 69 passed, including worker concurrency and record transactions;
  the subsequent legacy weekly-writer check passed separately (one test).
- React: 628 tests passed across 97 files; application/test/Vite TypeScript checks
  passed.
- Chromium: two Matchup checks passed at 1280px and 390px against
  `http://127.0.0.1:18448`. Authentication and API payloads were isolated fixtures.
  They verify full-count colors, spacing, both teams, reload, pending results,
  corrections, already-open rollover, expired historical replies and overflow.
  These checks establish rendering/lifecycle behavior, not production data.
- Disposable PostgreSQL migration certificate: full-chain upgrade through 0122,
  unchanged legacy scores/records, no fabricated receipt, downgrade/re-upgrade
  and Alembic ORM parity passed. No production/browser database was migrated.
- Final local web build/Capacitor sync and signed generic-device iOS build passed;
  code signatures/capabilities and packaged web assets were verified. No full
  combined app installation or live APNs send.

Focused evidence lives in `tests/api/test_matchup_record_highlights.py`,
`web/client/components/league/MatchupRecord.spec.tsx`,
`web/client/hooks/use-league-matchup-context.spec.tsx`,
`web/tests/e2e/matchup-record-highlight.spec.ts` and
`scripts/certify_matchup_record_migration.py`. Cases include multi-digit counts,
league/season switching, missing/failed application, ties/byes, correction
receipts, idempotence and transaction rollback.

## Remaining release limits

The installed UI-only iPhone package does not include this feature. The combined
API migration and client must ship together after release authorization. Existing
legacy finalized matchups remain neutral until a normal scorer recalculation
certifies them. Physical push delivery remains unverified; see
`native-ios-push.md` for the specific provider/device prerequisites.
