SHELL := /bin/bash
COMPOSE_PROJECT_NAME ?= cff_local
COMPOSE := COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker compose

.PHONY: help env db-up db-down migrate api web dev bootstrap test-backend test-web test-e2e

help:
	@echo "CollegeFootballFantasy local commands"
	@echo "  make env            # create the ignored worktree-local .env and enable ESPN history imports"
	@echo "  make bootstrap      # sync deps, install web deps, run db + migrations"
	@echo "  make dev            # start DB + API + UI together"
	@echo "  make api            # start API only (localhost:8000)"
	@echo "  make web            # start web only (localhost:5173)"
	@echo "  make migrate        # run alembic migrations"
	@echo "  make test-backend   # run backend tests"
	@echo "  make test-web       # run web typecheck + unit tests"
	@echo "  make test-e2e       # run Playwright critical browser tests"

env:
	python3 scripts/ensure_local_env.py --enable-espn-historical-stats

db-up:
	$(COMPOSE) up -d db

db-down:
	$(COMPOSE) down

migrate:
	uv run alembic -c api/alembic.ini upgrade head

api:
	PYTHONPATH=. uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port 8000

web:
	npm --prefix web run dev -- --host 0.0.0.0

dev:
	./scripts/dev.sh

bootstrap: env db-up
	uv sync
	npm --prefix web ci
	$(MAKE) migrate

test-backend:
	PYTHONPATH=. uv run pytest -q tests

test-web:
	npm --prefix web run typecheck
	npm --prefix web test

test-e2e:
	npm --prefix web run test:e2e
