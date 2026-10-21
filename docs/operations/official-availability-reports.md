# Official availability reports

The injury/status importer uses only these public conference report pages:

- SEC: `https://www.secsports.com/fbreports`
- Big 12: `https://big12sports.com/sports/2025/8/14/FBreporting.aspx`
- ACC: `https://theacc.com/sports/2025/8/28/availability-reporting-football.aspx`
- Big Ten: `https://bigten.org/fb/availability-reports/`

Create a Railway Cron service with the production API variables and select
`railway.availability-scheduler.toml` as its Railway config file. It runs this
command:

```sh
uv run python scripts/sync_official_availability_reports.py --season 2026
```

Configure the Railway schedule as `*/30 * * * *` (UTC). The job runs every 30
minutes, including Thursday/Friday report updates and game-day final reports.
The former Wednesday/Sunday 10 AM schedule missed those changes. No paired
EST/EDT hours or local weekday filter is needed. The command calculates the
football week from the shared calendar; `--week` is reserved for deliberate
backfills. It is idempotent: unchanged designations do not duplicate news or
rostered-manager injury alerts.

Each conference uses an independent transaction and freshness record, scoped
by season/week/conference. A broken source cannot roll back healthy sources
or mark the entire P4 feed ready. Partial failures exit nonzero after recording
the failed sources, while successful imports remain committed. Counts are
stored with each successful source health record.

Use the API Docker image for this Cron service. It contains Chromium and the
public-page renderer required by the conference report apps; no undocumented
vendor API is used. If a report does not render as a supported public table, dated grouped report cards, or its
explicit no-games state, the run fails and its provider sync state records the
failure rather than reporting an empty successful update.

Grouped cards require a dated Games heading, explicit status groups and
jersey-labelled player names. SEC/ACC/Big Ten team identity comes from public
headings or logo labels. Big Ten range headings use each game’s dated footer.
Big 12 publishes generic logo labels; those rows require a unique exact
name/position match within Big 12 and a real game on the report date. Ambiguous
identities are skipped. The Big Ten’s public report redirect is resolved only
to its explicitly linked HDI report document. Dated rows must match an actual game in the
requested season/week before they can update a player.

Only exact existing P4 QB/RB/WR/TE/K matches are imported. An unknown name,
an ambiguous name, or an unsupported position is skipped and never creates a
new player or status. A missing row is not treated as an Active designation.

The source status remains `OUT` unless the official report explicitly says IR
or supplies an absence of **at least four weeks/games** (including
season-ending). A `2-4 week` range is intentionally kept as `OUT` because the
earliest stated return is under four weeks.

## Reviewed reports and week rollover

The scheduled command also reads `reports/availability/2026-reviewed-corrections.json`.
Each entry requires an exact existing player/school/position identity, two public
reports, the source publication timestamp and an explicit effective week window.
Reports are applied once through the existing audited correction tool before the
conference fetches, so a pending vendor page cannot roll them back. A late run
writes only the current week. The job never changes actual points or completed
week records, invents a projection, creates a player, or treats a missing name as
healthy. Confirmed absences can be saved during a bye even without a projection.

The API carries bounded reviewed absences across byes until their window ends.
A verified later return clears an old season-ending or multiweek absence. A dated
conference report for a later game can supersede an older manual report; the
same-week manual protection is retained. Ordinary weekly OUT/Questionable rows
are not blindly copied into a new week.

An explicit report-pending page is recorded as `pending`, without advancing its
last successful import timestamp. An unreadable page remains `failed`. ACC range
headings use the game footer date, including uppercase Friday/Saturday footers.
Every run saves a full canonical player-pool coverage receipt under provider
`reviewed_availability_audit`, feed `player_pool`, scoped by season/week. Its
`unreported` count is an evidence gap, not a claim those players are healthy.
