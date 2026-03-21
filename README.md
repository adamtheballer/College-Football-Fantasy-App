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

## Environment variables

See `.env.example` for the full list.

- `DATABASE_URL`
- `DB_PORT`
- `API_HOST`
- `API_PORT`
- `API_LOG_LEVEL`
- `UI_BASE_URL`

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
