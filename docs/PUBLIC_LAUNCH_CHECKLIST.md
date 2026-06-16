# Public Launch Checklist

The project is not public-launch-ready until every P0 and P1 item is complete.

## Current Recommendation

- Internal alpha: allowed after tests pass.
- Friends beta: blocked until Docker verification and shared-backend smoke testing pass.
- Public launch: blocked until redraft season systems, playoffs, deployment, monitoring, backup, and support workflows pass.

## P0 Gates

- [ ] Dirty tree stabilized into intentional commits.
- [ ] Managed cloud staging deploy works.
- [ ] Managed cloud production deploy works.
- [ ] Migrations pass on empty DB and previous release DB.
- [ ] `/health` passes in production.
- [ ] `/health/ready` passes in production.
- [ ] Manual shared-backend smoke test passes.
- [ ] Worker ownership prevents duplicate draft/scoring/time-sensitive processing.
- [ ] Real draft is safe under simultaneous users.
- [ ] Roster/lineup locks are enforced from schedule data.
- [ ] Waivers process atomically.
- [ ] Trades complete atomically and roster-legally.
- [ ] Weekly scoring and standings recompute reliably.
- [ ] Playoff bracket generation, seeding lock, advancement, and champion finalization are implemented.
- [ ] Production monitoring, alerting, backups, and rollback are tested.

## P1 Gates

- [ ] Docker Compose clean-volume boot passes.
- [ ] Auth/session abuse hardening is complete.
- [ ] Commissioner-only actions are audited.
- [ ] Public settings are all enforced or clearly disabled.
- [ ] Streamlit and starter backend paths are removed from production deployment.
- [ ] Playwright critical user flows pass.
- [ ] Mobile/responsive smoke test passes.
- [ ] Provider data import and refresh runbooks are tested.
- [ ] API collections are updated for supported flows.

## In-Progress Evidence

- Local dev boot reliability: API and UI now consistently use `http://localhost:8000` and `http://localhost:8080`; `make dev-local` starts both without Docker when an existing database is available.
- Auth/session abuse hardening: failed-login throttling is implemented for `/auth/login`. This is not complete enough to check the P1 auth gate; remaining work includes distributed rate limiting, signup throttling, refresh abuse controls, and production proxy/IP trust policy.

## Feature Readiness Targets

- Auth/session: 9/10 before public launch.
- League create/join/settings: 9/10.
- Drafts: 9/10.
- Mock drafts: 8/10.
- Rosters/lineups: 9/10.
- Waivers: 8/10.
- Trades: 8/10.
- Scoring/matchups/standings: 9/10.
- Playoffs: 8/10.
- Deployment/operations: 9/10.

## Final Sign-Off Evidence

- Backend test transcript.
- Frontend typecheck/test/build transcript.
- Migration smoke transcript.
- Docker Compose smoke transcript.
- Managed staging smoke transcript.
- Managed production smoke transcript.
- Shared-backend manual smoke results.
- Backup restore drill notes.
- Known limitations approved for release.
