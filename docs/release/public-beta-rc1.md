# Public Beta Release Candidate Gate

This branch is a release candidate, not the deployment branch. Promote it to `main` only after every item below is evidenced for the exact commit being promoted.

## Automated evidence

- GitHub Actions **CI** is required for pull requests to `main` and pushes to `main`.
- The required checks are `verify`, `docker-clean-boot`, and `real-stack-e2e`.
- The workflow uploads Playwright reports, real-stack logs, and isolated-stack logs even when a job fails.
- `/health/runtime` returns the API build SHA and Alembic readiness state. The Settings page displays the web build SHA and API build SHA together.

## Required GitHub configuration

Repository administrators must configure branch protection (or rulesets) for `main` to require the three CI checks above before merge. This cannot be enforced by repository code alone.

## Promotion sequence

1. Build API and web artifacts with the same immutable commit SHA in `APP_BUILD_SHA` and `VITE_BUILD_SHA`.
2. Take and verify the managed-database backup.
3. Run `alembic upgrade head` against staging, then verify `scripts/check_alembic_head.py`.
4. Run the required CI checks and record the workflow URL and artifact links.
5. Deploy to staging and verify `/health/runtime` reports the intended SHA and `status: ready`.
6. Run the documented beta smoke flows against staging before merging the exact release-candidate commit to `main`.
7. Tag the promoted commit, deploy it, and repeat the runtime identity check in production.

## Rollback

Rollback the web and API to the prior tagged artifact only after confirming the database migration is backward compatible. If it is not, restore from the verified pre-migration backup using the provider's documented procedure.
