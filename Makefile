SHELL := /bin/bash

.PHONY: help db-up db-down migrate api web dev bootstrap test-backend test-web test-e2e

help:
	@echo "CollegeFootballFantasy local commands"
	@echo "  make bootstrap      # sync deps, install web deps, run db + migrations"
	@echo "  make dev            # start DB + API + UI together"
	@echo "  make api            # start API only (localhost:8000)"
	@echo "  make web            # start web only (localhost:5173)"
	@echo "  make migrate        # run alembic migrations"
	@echo "  make test-backend   # run backend tests"
	@echo "  make test-web       # run web typecheck + unit tests"
	@echo "  make test-e2e       # run Playwright critical browser tests"

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	uv run alembic -c api/alembic.ini upgrade head

api:
	uv run uvicorn api.app.main:app --host 0.0.0.0 --port 8000

web:
	npm --prefix web run dev -- --host 0.0.0.0

dev:
	./scripts/dev.sh

bootstrap: db-up
	uv sync
	npm --prefix web install
	$(MAKE) migrate

test-backend:
	PYTHONPATH=. uv run pytest -q tests

test-web:
	npm --prefix web run typecheck
	npm --prefix web test

test-e2e:
	npm --prefix web run test:e2e
