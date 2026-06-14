# CollegeFootballFantasy

Fantasy football research + roster helper for college leagues. The supported UI is the React app in `web/`, backed by the FastAPI API over HTTP.

## Quickstart

1) Install dependencies

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

2) Copy env and update values if needed

```bash
cp .env.example .env
```

The default local Postgres port is `5433` to avoid collisions with other local database services. If you already run Postgres on another port, update `DATABASE_URL` and `DB_PORT` together in `.env`.

3) Start Postgres

```bash
docker compose up -d db
```

4) Run migrations

```bash
PYTHONPATH=. uv run alembic -c api/alembic.ini upgrade head
```

5) Install web dependencies

```bash
cd web && npm install
```

6) Start API and UI

```bash
PYTHONPATH=. uv run uvicorn api.app.main:app --host 0.0.0.0 --port 8000
cd web && npm run dev
```

Or run the helper script:

```bash
./scripts/dev.sh
```

Or use Make targets:

```bash
make bootstrap
make dev
```

Common verification commands:

```bash
make test-backend
make test-web
docker compose up --build
```

Local dev URLs:

- UI: `http://localhost:5173`
- API: `http://localhost:8000`

## Testing Multiplayer Mock Drafts With Friends

`localhost` is not shareable. A link like `http://localhost:5173` only works on the developer machine running Vite. To test multiplayer mock drafts with friends while still editing locally with hot reload, expose the local frontend and backend with public tunnel URLs or deploy public dev URLs.

Keep the normal local dev workflow running:

```bash
PYTHONPATH=. uv run uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --reload
cd web && npm run dev
```

Then point public tunnels at those local servers:

- Frontend public URL forwards to `http://localhost:5173`
- Backend public URL forwards to `http://localhost:8000`

Backend `.env` for public tunnel testing:

```bash
PUBLIC_WEB_URL=<public frontend URL>
PUBLIC_API_URL=<public backend URL>
UI_BASE_URL=<public frontend URL>
API_PUBLIC_MODE=true
```

Frontend `web/.env` for public tunnel testing:

```bash
VITE_API_BASE_URL=<public backend URL>
VITE_PUBLIC_WEB_URL=<public frontend URL>
```

After changing env variables, restart both frontend and backend so Vite and FastAPI reload the new URLs. Create a mock draft, copy the public invite link, and send that link to friends. If your invite link starts with `localhost`, it will not work for friends.

Auth cookie settings matter because multiplayer requires accounts:

- Local-only development: keep `REFRESH_COOKIE_SECURE=false`, `REFRESH_COOKIE_SAMESITE=lax`, and `REFRESH_COOKIE_DOMAIN=` unless you have a specific local domain setup.
- Public tunnel testing: keep local auth behavior unless your tunnel/browser combination requires cross-site cookies; if the frontend and backend use different public domains and refresh cookies fail, test `REFRESH_COOKIE_SECURE=true` with HTTPS and evaluate whether `REFRESH_COOKIE_SAMESITE=none` is required.
- Production: use `REFRESH_COOKIE_SECURE=true`; use `REFRESH_COOKIE_SAMESITE=lax` for same-site frontend/API domains, or `none` only when cross-site cookies are required; set `REFRESH_COOKIE_DOMAIN` to match the chosen public domain strategy.

Development checklist:

- Local-only:
  - Frontend: `http://localhost:5173`
  - Backend: `http://localhost:8000`
  - Invite links are local-only
- Public tunnel:
  - Frontend public tunnel points to `localhost:5173`
  - Backend public tunnel points to `localhost:8000`
  - `PUBLIC_WEB_URL` uses the frontend tunnel
  - `VITE_API_BASE_URL` uses the backend tunnel
  - CORS includes the frontend tunnel origin
- Production:
  - `PUBLIC_WEB_URL=https://yourdomain.com`
  - `VITE_API_BASE_URL=https://api.yourdomain.com`
  - CORS includes `https://yourdomain.com`
  - Cookies/auth settings are secure

## Environment variables

See `.env.example` for the full list.

- `DATABASE_URL`
- `DB_PORT`
- `ENVIRONMENT`
- `API_HOST`
- `API_PORT`
- `API_LOG_LEVEL`
- `UI_BASE_URL`
- `PUBLIC_WEB_URL`
- `PUBLIC_API_URL`
- `API_PUBLIC_MODE`
- `CORS_ORIGINS`
- `JWT_SECRET_KEY`

`UI_BASE_URL` should match your local web origin (`http://localhost:5173` for Vite dev).
`PUBLIC_WEB_URL` is the frontend URL used when the backend generates mock draft invite links.
`PUBLIC_API_URL` documents the externally reachable backend URL for public tunnel or production mode.
`CORS_ORIGINS` is a comma-separated allowlist for browser origins that can call the API.
`ENVIRONMENT=production` requires replacing the default `JWT_SECRET_KEY`; the API refuses to boot in production with `change-me-in-production`.

Sports provider/cache variables:

- `SPORTSDATA_API_KEY`
- `SPORTSDATA_ENABLED`
- `SPORTSDATA_*_PATH` endpoint templates
- `SPORTSDATA_*_TTL_DAYS` per-feed cache TTL
- `PROVIDER_DEFAULT_CACHE_TTL_DAYS` fallback TTL

The API uses DB-backed provider cache state (`provider_sync_states`) with feed+scope keys, expiry, status, and failure metadata.

## Migrations (Alembic)

Generate a new migration:

```bash
PYTHONPATH=. uv run alembic -c api/alembic.ini revision --autogenerate -m "message"
```

Apply migrations:

```bash
PYTHONPATH=. uv run alembic -c api/alembic.ini upgrade head
```

## API tests (pytest)

```bash
PYTHONPATH=. uv run pytest -q tests
```

## SportsData sync + DB cache workflow

Manual feed sync (DB-backed, idempotent):

```bash
PYTHONPATH=. uv run python scripts/sync_sportsdata_feeds.py --feed all --season 2025 --week 1
```

Useful scoped runs:

```bash
# reference players
PYTHONPATH=. uv run python scripts/sync_sportsdata_feeds.py --feed players

# schedule only
PYTHONPATH=. uv run python scripts/sync_sportsdata_feeds.py --feed schedule --season 2025

# standings for one conference
PYTHONPATH=. uv run python scripts/sync_sportsdata_feeds.py --feed standings --season 2025 --conference SEC

# injuries with fallback behavior
PYTHONPATH=. uv run python scripts/sync_sportsdata_feeds.py --feed injuries --season 2025 --week 1 --conference ALL
```

Injury provider preference:

1. Try SportsData injuries feed when enabled and key is configured.
2. If SportsData is unavailable/empty, fallback to Rotowire ingestion.
3. Persist normalized Power-4 injury rows in DB and serve from DB/API cache.

## News / Transfer Wire

- College Football News source URL: `https://collegefootballnews.com/`.
- Use RSS/feed/index metadata only; do not scrape full article pages.
- Do not store full article text, bypass protections, or copy full articles.
- Always link users back to the original source.
- News ingestion is manual/background and must not run on every homepage request.

Run ingestion manually:

```bash
PYTHONPATH=. uv run python scripts/sync_news_feeds.py --source cfn --limit 50
```

Seed the default College Football News source:

```bash
PYTHONPATH=. uv run python scripts/seed_news_sources.py
```

Manual fallback for testing or admin curation: `POST /news/manual`.

## Bruno workflow tests

1) Open Bruno
2) Load collection from `bruno/collections/backend-api`
3) Select environment `bruno/environments/local.env`
4) Run the requests in order, or use the sequence in `_Workflows/HappyPath.bru`

## Local development with Docker

Bring up everything in Docker:

```bash
docker compose up --build
```

API runs on `http://localhost:8000`, UI runs on `http://localhost:8080`.

## Draft System Notes

- Real league drafts write both `draft_picks` and `roster_entries`; this is intentional because completed live picks fill league rosters.
- Each real league is constrained to one `drafts` row. A completed real draft cannot be restarted or replaced by creating a second real draft for that league.
- Real draft pick creation locks the `drafts` row, recalculates the current pick under that lock, writes the `draft_picks` row and matching `roster_entries` row in one transaction, and converts expected uniqueness races into HTTP 409 conflicts.
- Real drafts currently transition from `scheduled` to `live` on the first successful pick as an intentional MVP behavior.
- When the final real draft pick is made, `drafts.status` becomes `completed` and `leagues.status` becomes `post_draft`.
- League creation and join flows require an authenticated user. The creator becomes commissioner, joins as the first member, receives a team, and gets a generated invite code/link. Invite-code joins reject duplicate members, full leagues, and completed drafts.
- Draft rooms read the player pool from the backend `players` table. Import the Google Sheet before drafting:
  `uv run python scripts/import_players_from_google_sheet.py --url "https://docs.google.com/spreadsheets/d/1NMP3EJSMbdRd7HDA0t7TwxzJ9DM_bUynLoRCgE6Ml74/export?format=csv&gid=0"`.
- If Google Sheets is unavailable, export CSV manually and run:
  `uv run python scripts/import_players_from_google_sheet.py --csv ./data/players.csv`.
- See `docs/draft-room.md` for column aliases, dry-run usage, and verification steps.
- Mock drafts use separate mock draft tables and must not write real league `draft_picks`, `roster_entries`, `leagues.status`, or `drafts.status`.
- Standalone multiplayer mock drafts use `mock_draft_sessions`, `mock_draft_participants`, `mock_draft_picks`, and `mock_draft_events`; rosters/results are derived from mock picks.
- Real draft order uses persisted `draft_order_team_ids` metadata when configured; otherwise it falls back to deterministic join order: teams ordered by `created_at`, then `id`.
- Mock draft order is randomized once by the backend at the scheduled start time and persisted on participants.
- Draft room multiplayer freshness uses websocket updates plus React Query polling. The polling fallback is faster for active drafts and slower for idle rooms.
- Pick timer state is backend-backed through `current_pick_started_at`, `current_pick_expires_at`, and draft timer state rows. Auto-pick endpoints enforce expired clocks; automatic background enforcement depends on the draft timeout runner being enabled and running.
- Backend player availability is the source of truth for draft boards. `/players?available_only=true&league_id=<id>` excludes both players already on league rosters and players already selected in the active league draft.
- Draft player search is server-filtered by name, school, and position; frontend filtering is display-only safety, not availability authority.
- The Streamlit `ui/` league page is legacy/dev-only and intentionally disabled for league creation/settings. Use the React `web/` app so nested league basics, settings, and draft payloads persist correctly.
- Trade analysis shown in the app is a basic local estimate based on roster/projection inputs. Schedule context is neutral unless a backend comparison endpoint supplies deeper matchup context.
- Current MVP limitation: real drafts do not yet have a dedicated explicit `draft_order` table beyond persisted draft-order metadata and fallback join order.

## Local Multiplayer League Testing

Use one normal Chrome window and one Chrome Incognito window as two different users:

1. Start FastAPI and React against the same local database.
2. Create a league while signed in as user A.
3. Copy the invite code/link from the league creation screen.
4. Sign in as user B in Incognito and join the league by code.
5. Refresh both browsers and confirm both users see the same league, member count, draft status, and draft room state.
6. For a scheduled/live real draft, use the temporary Draft navigation entry or the league card draft action; after completion, rosters should be visible from the Roster tab and the Draft entry should no longer appear.
7. Use the bottom plus action for mock drafts. Mock drafts remain standalone and must not create real league draft picks or roster entries.

For another device or tunnel, configure the existing public URL environment variables and keep both browser sessions pointed at the same backend/database. Do not expose secrets in frontend env files.

Mock draft retention cleanup:

```bash
PYTHONPATH=. uv run python scripts/cleanup_mock_drafts.py
```

Unsent completed mock drafts are eligible for cleanup after their 24-hour `expires_at`; emailed histories set `should_preserve_history=true` and extend `expires_at` for the preserved window.
