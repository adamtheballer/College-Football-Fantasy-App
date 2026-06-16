# Release Readiness

## Current Verdict

The app is safe for internal alpha testing only until all friends-beta gates below pass.

Public publishing is not approved. Do not describe this project as public-beta-ready.

## Latest Hardening Status

- Docker Compose verification: blocked in the current environment because the Docker CLI is unavailable. A Docker-capable machine must run the commands in the Docker Verification section before friends beta.
- Multi-device shared-backend smoke test: not run. Use `docs/MANUAL_SMOKE_TEST.md` and record results before friends beta.
- Frontend bundle status: pass. Route-level code splitting removed the Vite chunk-size warning during `npm --prefix web run build`.
- Playoff scope: out of scope. Playoff bracket generation, seeding locks, and matchup advancement are not implemented or advertised as working.
- Public launch operations: use `docs/DEPLOYMENT_RUNBOOK.md`, `docs/OPERATIONS_RUNBOOK.md`, and `docs/PUBLIC_LAUNCH_CHECKLIST.md`.

## Friends Beta Gate

Friends beta is allowed only when every item is true:

- Docker Compose has been run from a clean database with `docker compose down -v` and `docker compose up --build`.
- The API starts after Alembic migrations run automatically.
- The web app starts and can reach the configured API URL.
- Backend tests, frontend typecheck, frontend tests, and frontend build pass.
- Trade completion is either roster-legal and tested, or disabled honestly in the API and UI.
- Playoff brackets, seeding locks, and playoff matchup advancement are explicitly out of scope and not claimed as supported.
- Critical signup, league create/join, real draft, mock draft, roster, waiver, trade, scoring, and standings flows have been manually smoke-tested against one shared backend/database.

## Docker Verification

Docker verification remains environment-dependent. If Docker is unavailable in the current coding environment, run these commands on a Docker-capable machine before friends beta:

```bash
docker compose down -v
docker compose up --build
```

Then verify:

- API health is reachable at `http://localhost:8000/health`.
- API readiness is reachable at `http://localhost:8000/health/ready`.
- UI is reachable at `http://localhost:8080`.
- Migrations apply without manual intervention before Uvicorn serves requests.
- Browser API calls succeed with the configured `VITE_API_BASE_URL`.

Recommended human-run verification transcript:

```bash
docker compose down -v
docker compose up --build
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8080/
```

Do not mark this section complete from code inspection alone.

## Multi-Device Smoke Test

Status: not run.

Checklist: `docs/MANUAL_SMOKE_TEST.md`.

Friends beta requires the checklist to pass against one shared backend and database using two browsers, browser profiles, or devices. The test must cover auth refresh, league create/join, single-player mock draft isolation, real draft update behavior, duplicate/wrong-user pick rejection, player availability search, and trade behavior.

## Bundle Status

Status: pass.

The production build uses route-level code splitting. The current build completes without Vite's chunk-size warning. Re-run `npm --prefix web run build` after major page, chart, animation, or draft-room UI changes.

## Trade Status

Trade proposal and completion are enabled for alpha.

Trade completion must remain server-authoritative:

- both teams must belong to the offer league;
- both managers must still own their teams and be league members;
- both sides must still own the offered players at completion time;
- duplicate players in a trade are rejected;
- completed swaps must preserve roster size and slot limits;
- failures must rollback roster, trade status, transaction, and audit mutations.

The Trade page displays a basic estimate only. It does not replace backend roster legality checks.

## Playoff Scope

Playoffs are out of scope for internal alpha and friends beta.

Implemented today:

- regular-season schedule generation;
- matchup scoring;
- standings snapshots;
- persisted `playoff_teams` setting for future seeding.

Not implemented:

- playoff bracket generation;
- playoff seeding locks;
- playoff matchup advancement;
- playoff championship flow.

UI and docs must not claim playoff brackets are supported until those systems exist.

## Known Limitations

- Docker Compose must still be verified on a machine with Docker before external testers rely on it.
- Two scoring APIs currently coexist: legacy weekly score endpoints and the newer auditable recompute endpoint.
- Stat corrections are supported by recomputing/finalizing week scores, but there is no dedicated stat-correction review workflow yet.
- Roster locks depend on current week/game schedule data being present.
- Live draft rooms use websocket updates with React Query polling fallback.
- Mock drafts are persisted in separate mock draft tables and must not mutate real league rosters or draft rows.
- Automated playoff systems are not implemented.

## Public Publishing Blockers

Do not publish publicly until:

- Docker deployment has been verified repeatedly from a clean DB;
- scoring paths are unified or clearly operationally separated;
- playoff brackets/seeding/advancement are implemented or the product is explicitly season-MVP without playoffs;
- stat-correction and commissioner audit workflows are production-ready;
- multi-device manual testing has completed with real users against a shared backend/database.

## Critical Flow Readiness

- Auth: backend and frontend use `GET /auth/me` for session bootstrap.
- Create/join league: enabled for alpha; duplicate joins, full leagues, and completed-draft joins are covered by backend tests.
- Single-player mock draft: enabled for alpha; mock drafts use separate mock draft tables and must not mutate real league rosters or real draft rows.
- Real draft: enabled for alpha; draft picks are server-authoritative and protected by backend conflict handling.
- Player search: backend availability filtering is the source of truth for draft player pools.
- Roster updates: enabled for alpha; roster and lineup mutations enforce configured lock rules when schedule data is available.
- Trades: proposal and completion are enabled for alpha; completion must remain server-authoritative and roster-legal.
- Playoffs: out of scope; stored `playoff_teams` is a future setting only and does not activate playoff brackets.

## Remaining Blockers

- P1: Docker Compose clean-volume verification must pass on a Docker-capable machine.
- P2: `docs/MANUAL_SMOKE_TEST.md` must be executed and recorded against one shared backend/database.
- P3: Playoff systems remain out of scope and must not be advertised as implemented.
