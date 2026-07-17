# CollegeFootballFantasy

Fantasy football research + roster helper for college leagues. The supported UI is the React app in `web/`, backed by the FastAPI API over HTTP.

## Backend strategy

This repo has one supported backend: the FastAPI app under `api/`.

- Canonical API import path: `collegefootballfantasy_api.app.main:app`
- Canonical local API command: `PYTHONPATH=. uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port 8000`
- Canonical frontend: React/Vite in `web/`
- Express/Vite server middleware is not part of the supported product backend.

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

Migrations also seed the CFB27 player board into `players`, so clean databases do not require a separate manual `sync_cfb27_ratings.py` run before Player Compare works.
`api/app/data/cfb27_ratings.json` is the source of truth for CFB27 ratings. Regenerate the frontend module after changing it:

```bash
PYTHONPATH=. uv run python scripts/generate_cfb27_frontend.py
PYTHONPATH=. uv run python scripts/generate_cfb27_frontend.py --check
```

5) Install web dependencies

```bash
cd web && npm ci
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
- `ENVIRONMENT`
- `API_HOST`
- `API_PORT`
- `API_LOG_LEVEL`
- `UI_BASE_URL`
- `CORS_ORIGINS`
- `CORS_ORIGIN_REGEX`
- `JWT_SECRET_KEY`
- `JWT_ACCESS_TOKEN_TTL_MINUTES`
- `REFRESH_TOKEN_TTL_DAYS`
- `REFRESH_COOKIE_NAME`
- `REFRESH_COOKIE_SECURE`
- `REFRESH_COOKIE_SAMESITE`
- `REFRESH_COOKIE_DOMAIN`
- `ALLOW_LEGACY_API_TOKEN_AUTH`
- `AUTH_EMAIL_VERIFICATION_TTL_HOURS`
- `AUTH_RESEND_VERIFICATION_RATE_LIMIT`
- `CHAT_MESSAGE_RATE_LIMIT`
- `CHAT_MESSAGE_RATE_LIMIT_WINDOW_MINUTES`
- `CHAT_MESSAGE_SUSTAINED_RATE_LIMIT`
- `CHAT_MESSAGE_SUSTAINED_RATE_LIMIT_WINDOW_MINUTES`
- `CHAT_DIRECT_THREAD_RATE_LIMIT`
- `CHAT_DIRECT_THREAD_RATE_LIMIT_WINDOW_MINUTES`
- `CHAT_READ_RATE_LIMIT`
- `CHAT_READ_RATE_LIMIT_WINDOW_MINUTES`
- `CHAT_EDIT_WINDOW_MINUTES`
- `EMAIL_DELIVERY_MODE`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`
- `SCORING_PROVIDER`
- `SCORING_ALLOW_UNOFFICIAL_PROVIDERS`
- `SCORING_WORKER_INTERVAL_LIVE_SECONDS`
- `SCORING_WORKER_INTERVAL_POSTGAME_SECONDS`
- `SCORING_WORKER_INTERVAL_CORRECTION_SECONDS`
- `SCORING_WORKER_RETRY_MAX_ATTEMPTS`
- `SCORING_WORKER_RETRY_BASE_SECONDS`
- `SUPPORT_EMAIL`
- `PRIVACY_POLICY_URL`
- `TERMS_URL`
- `PROVIDER_DISCLOSURE_URL`
- `SECURITY_HEADERS_ENABLED`

`UI_BASE_URL` should match your local web origin (`http://localhost:5173` for Vite dev).

Production must use:

- `ENVIRONMENT=production`
- an explicit, non-default `JWT_SECRET_KEY`
- explicit HTTPS `CORS_ORIGINS` for the deployed web app
- `CORS_ORIGIN_REGEX=` blank unless there is a production-safe regex requirement
- `REFRESH_COOKIE_SECURE=true`
- `REFRESH_COOKIE_SAMESITE=lax` or stricter unless the deployment requires cross-site cookies
- `EMAIL_DELIVERY_MODE=smtp` or another production mail adapter
- valid SMTP sender configuration so password-reset links are deliverable
- `SCORING_PROVIDER=sportsdata` or another licensed provider integration approved for production use
- `SUPPORT_EMAIL`, `PRIVACY_POLICY_URL`, `TERMS_URL`, and `PROVIDER_DISCLOSURE_URL` set to public support/legal pages

The API refuses to start in production with the `.env.example` JWT placeholder, default localhost CORS origins, wildcard CORS origins, or the default localhost CORS regex.
When SMTP delivery is enabled, production startup also requires `SMTP_HOST` and `SMTP_FROM_EMAIL`.
Production startup also rejects unofficial scoring providers such as ESPN/cache/mock unless `SCORING_ALLOW_UNOFFICIAL_PROVIDERS=true` is explicitly set for a non-public/staging deployment.

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

The CFB27 player pool is data-migration backed. `scripts/sync_cfb27_ratings.py` is a manual resync/repair helper, not a required setup step. `web/client/lib/cfb27Ratings.ts` is generated from `api/app/data/cfb27_ratings.json`; do not edit the frontend file by hand.

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
- `environments.production.api.readiness_path`: `/health/ready`

Production deploy order:

1. Install backend dependencies with `uv`.
2. Run Alembic migrations against the managed Postgres database.
3. Verify the managed database is at the repository Alembic head.
4. Start Uvicorn with `collegefootballfantasy_api.app.main:app`.
5. Require `GET /health/ready` to return `200` before routing traffic.
6. Build the Vite app with `npm --prefix web ci && npm --prefix web run build`.
7. Serve `web/dist/spa` from the static frontend host.

Useful migration verification command:

```bash
PYTHONPATH=. uv run python scripts/check_alembic_head.py
```

Readiness endpoints:

- `GET /health`: process liveness only.
- `GET /health/ready`: database connectivity plus Alembic migration readiness.

## CI and staging gates

Pull requests run `.github/workflows/ci.yml`, which starts a fresh Postgres service, imports the FastAPI app, runs Alembic migrations, verifies the database is at Alembic head, and then runs backend and frontend checks.

Staging database verification is manual/protected through `.github/workflows/staging-migration-check.yml`.

Required GitHub secrets for the staging workflow:

- `STAGING_DATABASE_URL`
- `STAGING_API_BASE_URL`

Production deployment must use a protected deployment job or provider hook that sets `DATABASE_URL` from `PRODUCTION_DATABASE_URL`, runs migrations, runs `scripts/check_alembic_head.py`, promotes the API, and confirms `/health/ready` before traffic is sent to the new release.

## Production operations

The public-beta operating model is documented in `docs/operations/production-operations.md`.

Production should run at least three separate processes:

- API process: `uvicorn collegefootballfantasy_api.app.main:app`
- Static web process/host: built Vite output from `web/dist/spa`
- Scoring worker process: `PYTHONPATH=. uv run python scripts/run_scoring_worker.py --season <year> --week <week> --mode live`
- Due trade processor: `PYTHONPATH=. uv run python scripts/process_due_trades.py`

Use `--mode postgame` for 10–30 minute postgame reconciliation and `--mode correction` for next-day correction sweeps.
Run the due trade processor every 5–15 minutes and once shortly after Monday reset so `accepted_pending` trades with `process_after` are completed.
