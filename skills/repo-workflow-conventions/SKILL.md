---
name: repo-workflow-conventions
description: Follow repo-specific development workflows for CollegeFootballFantasy, including setup, running services, and common commands. Use when answering “how do I run/build/test” questions for this repo.
---

# Repo Workflow Conventions

## Setup

- Install dependencies with `uv sync`.
- Copy `.env.example` to `.env` and update values as needed.

## Local services

- Start Postgres: `docker-compose up -d db`.
- Run migrations: `uv run alembic -c api/alembic.ini upgrade head`.
- Start API: `uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port 8000`.
- Start UI: `uv run streamlit run ui/app.py --server.port 8501`.
- Or use `./scripts/dev.sh` to run the stack.

## Testing

- Run API tests: `uv run pytest`.
- Run Bruno workflows: open Bruno, load `bruno/collections/backend-api`, select `bruno/environments/local.env`, run `_Workflows/HappyPath.bru`.
