# Official availability reports

The injury/status importer uses only these public conference report pages:

- SEC: `https://www.secsports.com/fbreports`
- Big 12: `https://big12sports.com/sports/2025/8/14/FBreporting.aspx`
- ACC: `https://theacc.com/sports/2025/8/28/availability-reporting-football.aspx`
- Big Ten: `https://bigten.org/fb/availability-reports/`

Create a Railway Cron service with the production API variables and this
command:

```sh
uv run python scripts/sync_official_availability_reports.py --season 2026
```

Use `0 10 * * *` with the service timezone set to `America/New_York` for the
daily 10:00 AM baseline. The command calculates the game week from the CFB
calendar; use `--week` only for a deliberate backfill or rehearsal. Conference
reports can change nearer to kickoff, so add a second game-day Cron refresh after
the conference's published availability deadline. The job is idempotent: retries
do not duplicate player news or rostered-manager injury alerts.

Use the API Docker image for this Cron service. It contains Chromium and the
public-page renderer required by the conference report apps; no undocumented
vendor API is used. If a report does not render as either a public table or its
explicit no-games state, the run fails and its provider sync state records the
failure rather than reporting an empty successful update.

Only exact existing P4 QB/RB/WR/TE/K matches are imported. An unknown name,
an ambiguous name, or an unsupported position is skipped and never creates a
new player or status. A missing row is not treated as an Active designation.

The source status remains `OUT` unless the official report explicitly says IR
or supplies an absence of **at least four weeks/games** (including
season-ending). A `2-4 week` range is intentionally kept as `OUT` because the
earliest stated return is under four weeks.
