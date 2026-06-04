# Draft Room Player Pool

The draft room reads players from the backend `players` table. React draft screens must not depend on hardcoded player arrays.

## Import From Google Sheet

Run migrations first, then import:

```bash
PYTHONPATH=. uv run alembic -c api/alembic.ini upgrade head
uv run python scripts/import_players_from_google_sheet.py --url "https://docs.google.com/spreadsheets/d/1NMP3EJSMbdRd7HDA0t7TwxzJ9DM_bUynLoRCgE6Ml74/export?format=csv&gid=0"
```

If the sheet is not public from your runtime, export it manually:

1. Open the Google Sheet.
2. Choose `File > Download > Comma Separated Values (.csv)`.
3. Save it as `./data/players.csv`.
4. Run:

```bash
uv run python scripts/import_players_from_google_sheet.py --csv ./data/players.csv
```

Dry run and limited imports:

```bash
uv run python scripts/import_players_from_google_sheet.py --csv ./data/players.csv --dry-run
uv run python scripts/import_players_from_google_sheet.py --csv ./data/players.csv --limit 100
```

The import is idempotent. Running it repeatedly updates existing players by `external_id` when present, otherwise by `name + position + school`.

## Required Columns

At least one alias from each group is required:

- Name: `name`, `player`, `player_name`, `full_name`
- Position: `position`, `pos`
- School: `school`, `team`, `college`, `college_team`, `university`

## Optional Columns

- External ID: `external_id`, `sportsdata_id`, `player_id_external`, `id`
- Image: `image_url`, `headshot`, `photo`, `player_image`
- Rank: `rank`, `overall_rank`, `draft_rank`, `big_board_rank`
- ADP: `adp`, `avg_draft_position`, `average_draft_position`
- Projected points: `projected_fantasy_points`, `fantasy_points`, `fpts`, `proj_points`, `projection`
- Projection stats: `pass_yards`, `pass_tds`, `interceptions`, `rush_yards`, `rush_tds`, `receptions`, `rec_yards`, `rec_tds`, `floor`, `ceiling`, `boom_prob`, `bust_prob`

## Verify Import

```bash
curl "http://localhost:8000/players?limit=10&sort=draft_rank"
```

Then enter a real or mock draft room. The Available Players table should show imported DB-backed players. If the table is empty, the UI shows an import instruction instead of failing silently.
