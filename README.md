# CollegeFootballFantasy

Fantasy football research + roster helper for college leagues. The supported UI is the React app in `web/`, backed by the FastAPI API over HTTP.

## Backend strategy

This repo has one supported backend: the FastAPI app under `api/`.

- Canonical API import path: `collegefootballfantasy_api.app.main:app`
- Canonical local API command: `PYTHONPATH=. uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port 8000`
- Canonical frontend: React/Vite in `web/`
- Unsupported legacy backend flow: Express/Vite server middleware under `web/server`

Do not start, deploy, or reintroduce an Express backend for product API routes. The `web/` package is a static/client app that calls the FastAPI API through the configured API base URL.

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
uv run alembic -c api/alembic.ini upgrade head
```

5) Install web dependencies

```bash
cd web && npm install
```

6) Start API and UI

```bash
PYTHONPATH=. uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port 8000
cd web && npm run dev
```

Backend import smoke check:

```bash
PYTHONPATH=. uv run python -c "from collegefootballfantasy_api.app.main import app; print(app.title)"
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

Local dev URLs:

- UI: `http://localhost:5173`
- API: `http://localhost:8000`

## Environment variables

See `.env.example` for the full list.

- `DATABASE_URL`
- `DB_PORT`
- `API_HOST`
- `API_PORT`
- `API_LOG_LEVEL`
- `UI_BASE_URL`

`UI_BASE_URL` should match your local web origin (`http://localhost:5173` for Vite dev).

Production must use an explicit, non-default `JWT_SECRET_KEY` and explicit `CORS_ORIGINS`. Do not deploy production with localhost-only origins or the `.env.example` secret placeholder.

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
uv run alembic -c api/alembic.ini revision --autogenerate -m "message"
```

Apply migrations:

```bash
uv run alembic -c api/alembic.ini upgrade head
```

## API tests (pytest)

```bash
uv run pytest
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

Docker Compose runs Alembic migrations before Uvicorn starts the API. If local port `5433` is already in use, override the database host port without changing the container network URL:

```bash
DB_PORT=55433 docker compose up --build
```

## Deployment configuration

Deployment environments are described in `deployments.yaml`.

The deployment config intentionally names FastAPI as the only backend runtime and Vite/React as the only frontend runtime. Dev and production deploy flows should read from that file rather than inventing a second backend path.

Key entries:

- `canonical_runtime.backend.import_path`: `collegefootballfantasy_api.app.main:app`
- `canonical_runtime.frontend.source_dir`: `web`
- `environments.dev`: local Docker Postgres + FastAPI + Vite
- `environments.production`: managed Postgres + FastAPI + static Vite build

Production deploy order:

1. Install backend dependencies with `uv`.
2. Run Alembic migrations against the managed Postgres database.
3. Start Uvicorn with `collegefootballfantasy_api.app.main:app`.
4. Build the Vite app with `npm --prefix web ci && npm --prefix web run build`.
5. Serve `web/dist/spa` from the static frontend host.
