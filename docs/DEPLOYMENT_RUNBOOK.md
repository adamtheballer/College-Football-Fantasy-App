# Managed Cloud Deployment Runbook

This app is not approved for public launch until this runbook passes in staging and production.

## Target Architecture

- Frontend: Vercel or equivalent static React/Vite hosting.
- API: Render, Fly.io, or equivalent managed service running FastAPI/Uvicorn.
- Database: managed Postgres such as Neon, Supabase, Render Postgres, or Fly Postgres.
- Worker: separate managed process for draft timeouts, scoring jobs, stats sync, notifications, and cleanup jobs.
- Error tracking: Sentry or equivalent for frontend and backend.
- Logs: platform logs plus structured backend request logs.

## Required Environment Variables

Backend:

- `DATABASE_URL`
- `ENVIRONMENT=production`
- `API_HOST=0.0.0.0`
- `API_PORT`
- `API_LOG_LEVEL`
- `UI_BASE_URL`
- `PUBLIC_WEB_URL`
- `PUBLIC_API_URL`
- `CORS_ORIGINS`
- `JWT_SECRET_KEY`
- `REFRESH_COOKIE_SECURE=true`
- `REFRESH_COOKIE_SAMESITE`
- provider API keys only in backend/worker environments

Frontend:

- `VITE_API_BASE_URL`
- `VITE_PUBLIC_WEB_URL`
- `VITE_WEB_PUSH_PUBLIC_KEY` if push notifications are enabled

## Deployment Sequence

1. Create managed Postgres database.
2. Set backend environment variables.
3. Run migrations before promoting API traffic:
   ```bash
   PYTHONPATH=. uv run alembic -c api/alembic.ini upgrade head
   ```
4. Start API:
   ```bash
   PYTHONPATH=. uv run uvicorn api.app.main:app --host 0.0.0.0 --port "$API_PORT"
   ```
5. Build and deploy frontend:
   ```bash
   npm --prefix web ci
   npm --prefix web run build
   ```
6. Verify API:
   ```bash
   curl -fsS "$PUBLIC_API_URL/health"
   curl -fsS "$PUBLIC_API_URL/health/ready"
   ```
7. Verify frontend loads and calls API from the production origin.

## Release Gates

- Backend tests pass.
- Frontend typecheck, tests, and build pass.
- Migrations pass from an empty DB and from the previous release DB.
- `/health` and `/health/ready` pass.
- Manual shared-backend smoke test passes.
- Worker ownership for timeout/scoring jobs is proven to avoid duplicate processing.
- Public launch checklist passes.

## Rollback

1. Stop new deploy promotion.
2. Roll API and web services back to the last known good release.
3. Do not roll back a database migration unless a tested downgrade exists.
4. If a migration caused data damage, restore a database backup into a recovery database first.
5. Document incident timeline and affected leagues.

## Known Launch Blockers

- Docker Compose must still be verified on a Docker-capable machine.
- Production worker separation is not complete while the API lifespan owns the draft timeout runner.
- Playoff engine is required for public redraft launch.
