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
uv run alembic -c api/alembic.ini upgrade head
```

5) Install web dependencies

```bash
cd web && npm install
```

6) Start API and UI

```bash
uv run uvicorn api.app.main:app --host 0.0.0.0 --port 8000
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
