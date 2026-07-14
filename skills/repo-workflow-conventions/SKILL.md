---
name: repo-workflow-conventions
description: Follow repo-specific development workflows for CollegeFootballFantasy, including setup, local services, builds, tests, and verification. Use when asked to set up, start, build, test, verify, or troubleshoot this repository.
---

# Repo Workflow Conventions

## Setup

- Install dependencies with `uv sync`.
- Install frontend dependencies with `npm --prefix web ci`.
- Copy `.env.example` to `.env` and update values as needed.

## Local services

- Start Postgres: `docker compose up -d db`.
- Run migrations: `uv run alembic -c api/alembic.ini upgrade head`.
- Start API: `PYTHONPATH=. uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port 8000`.
- Start the React UI: `npm --prefix web run dev -- --host 0.0.0.0`.
- Or use `./scripts/dev.sh` to run the stack.

## Testing

- Run backend tests: `PYTHONPATH=. uv run pytest -q tests`.
- Run frontend type checking and unit tests: `npm --prefix web run typecheck` and `npm --prefix web test`.
- Run the frontend build: `npm --prefix web run build`.
- Run Playwright tests when the task changes a covered browser workflow: `npm --prefix web run test:e2e`.
- Run Bruno workflows: open Bruno, load `bruno/collections/backend-api`, select `bruno/environments/local.env`, and run the requests in the sequence documented by `_Workflows/HappyPath.bru`.
- Verify the actual API and UI listening URLs from process output or health checks instead of assuming configured defaults.
