# CollegeFootballFantasy

Fantasy football research + roster helper for college leagues. Streamlit UI talks to FastAPI API over HTTP only.

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

3) Start Postgres

```bash
docker-compose up -d db
```

4) Run migrations

```bash
uv run alembic -c api/alembic.ini upgrade head
```

5) Start API and UI

```bash
uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port 8000
uv run streamlit run ui/app.py --server.port 8501
```

Or run the helper script:

```bash
./scripts/dev.sh
```

## Environment variables

See `.env.example` for the full list.

- `DATABASE_URL`
- `API_HOST`
- `API_PORT`
- `API_LOG_LEVEL`
- `UI_API_BASE_URL`

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
docker-compose up --build
```

API runs on `http://localhost:8000`, UI runs on `http://localhost:8501`.
