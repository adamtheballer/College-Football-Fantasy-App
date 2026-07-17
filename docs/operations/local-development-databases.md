# Local development databases

Use one persistent Docker Compose project for ordinary manual development:

```bash
COMPOSE_PROJECT_NAME=cff_local
DB_PORT=5433
API_PORT=8000
WEB_PORT=8080
ESPN_HISTORICAL_STATS_ENABLED=true
```

Run `make env` once in each worktree. It creates missing local configuration and adds these defaults without replacing explicit values. Start the persistent database with:

```bash
docker compose -p cff_local up -d
```

The persistent PostgreSQL volume is `cff_local_pgdata`. Do not use `docker compose down -v` for this stack.

Only one worktree's API should run against `cff_local_pgdata` at a time. Before switching the active worktree, stop its API and migrate the database from the worktree that will become active. Do not point different migration histories or model versions at the same persistent database.

Use isolated project names for disposable test or schema-experiment stacks:

```bash
COMPOSE_PROJECT_NAME=cff_test_feature DB_PORT=55440 docker compose up -d
COMPOSE_PROJECT_NAME=cff_test_feature docker compose down -v
```

The real-stack E2E command already defaults to an isolated `cff_real_e2e` project and non-default ports.
