# Controlled production player enrichment

This runbook restores player-card enrichment without provider calls from the
production API.  It is intentionally separate from canonical player, value,
and preseason-projection reconciliation.

## Current approved sources

| Category | Approved source | Authority | Status |
| --- | --- | --- | --- |
| Canonical player identity | `reports/source-imports/2026/player-identities.csv` | reviewed 2026 identity workbook, manifest `player-identities.manifest.json` | available; 814 rows |
| Preseason season projection | `reports/source-imports/2026/player-projections.csv` | reviewed 2026 projection workbook, manifest `player-projections.manifest.json` | available; 814 rows; not a weekly feed |
| ESPN IDs and biographies | none | an ESPN client exists, but it is disabled and is not an approved staged export | **BLOCKED** |
| Historical season totals | none | an ESPN historical parser and an approved-sheet importer exist, but no approved immutable 2026 import export is present | **BLOCKED** |
| 2026 schedules | no staged export | `scripts/import_2026_team_schedules.py` names the canonical schedule workbook, but a reviewed immutable snapshot is not checked in | **BLOCKED** |
| Weekly projections | none | approved season projections cannot be divided into weeks | **BLOCKED** |
| Completed weekly stats | none | provider integrations are disabled for beta; no approved staged box-score export exists | **BLOCKED** |

The fixture files under `vendor/espn-college-football-stats/tests/fixtures/`
are test fixtures only and must never be used as a production source.

## Staged source contract

All source files are operator-supplied local CSV files, outside Git. Each row
must include `provider`, `provider_player_id`, `provider_team_id`,
`provider_team_name`, `player_name`, `school`, and `position`. A reviewed
`verified-aliases.csv` may map exactly one `(provider, provider_player_id)` to
one canonical `player_id`; it is not a name-based escape hatch.

The matching outcome is always one of `EXACT`, `VERIFIED_ALIAS`, `AMBIGUOUS`,
`NOT_FOUND`, or `CONFLICT`. Only the first two are eligible to write. A staged
source row is never matched by name alone: school and canonical position are
required, and a pre-existing provider ID must agree with both.

Stage inputs are deliberately independent:

1. `identities` adds a verified `player_provider_ids` mapping plus supplied
   biography values. Headshots require `headshot_approved=true`; they remain
   hidden while `PLAYER_HEADSHOTS_ENABLED=false`.
2. `historical` imports supplied season totals and source metadata without
   manufacturing missing numeric fields or fantasy points.
3. `scripts/import_2026_team_schedules.py --source <approved-local-csv>`
   remains the separate, canonical team-schedule stage. It accepts local
   snapshots only. Player game logs derive from those team schedules, not
   copied player schedules.
4. `weekly-projections` remains blocked until a reviewed week-specific export
   is supplied. It requires every published numeric output in the source;
   absent values are rejected rather than synthesized. Do not use
   `scripts/build_weekly_projections.py` as a substitute for an approved
   weekly source.
5. `completed-stats` accepts only a verified completed-game JSON stats payload
   per player/week; it cannot create a schedule or a projection.

## Operator flow

1. Create a logical PostgreSQL backup outside Git, store its SHA-256 and file
   path in a private JSON manifest, and verify it is readable.
2. Run every staged command without `--apply`, save reports outside Git, and
   stop for any `AMBIGUOUS`, `NOT_FOUND`, or `CONFLICT` row.
3. Review the aggregate report and alias file. Do not add a fuzzy alias.
4. Run exactly one approved stage with `--apply --logical-backup-manifest`.
   The stage commits once or rolls back completely.
5. Run the same dry run again; already applied source rows must report
   `unchanged`.

Example (dry run only):

```sh
PYTHONPATH=. uv run python scripts/import_player_enrichment.py \
  --stage identities --input /secure/staging/espn-identities.csv \
  --verified-aliases /secure/staging/verified-aliases.csv
```

The command reports aggregate identity outcomes and source row numbers only. It
never fetches a provider, logs credentials, or prints raw provider payloads.
