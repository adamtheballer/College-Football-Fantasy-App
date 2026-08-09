# Public Beta Deployment Parity

Every release merged to `main` must promote the same commit to all three
canonical production processes before the browser is treated as healthy:

1. **Vercel web** — `college-football-fantasy-app`, root directory `web`.
2. **Railway API** — `College-Football-Fantasy-App`, root directory `/`.
3. **Railway lifecycle worker** — `lifecycle-worker`, root directory `/`.

`RuntimeCompatibilityGate` deliberately blocks a browser bundle when the web,
API, and worker release identities differ. The deployment sequence therefore is
not complete when only the web or worker has updated.

## Beta release gate

For a single merged `main` SHA:

1. Confirm Vercel completed the canonical web deployment for that SHA.
2. Confirm Railway created successful API and lifecycle-worker deployments for
   that same SHA.
3. Confirm `GET /health/ready` returns `200` from the API.
4. Confirm `GET /health/runtime` reports equal `git_sha`, `web_git_sha`, and
   `worker_git_sha` values matching the merged SHA.
5. Run the browser runtime-proxy verification before calling the release live.

The temporary Railway recovery configuration intentionally has no
`preDeployCommand`. It must remain unchanged until a separate hardening PR has
validated automatic migration execution outside production. `/health/ready`
continues to reject an unreachable database, a missing `alembic_version` table,
or a database revision that differs from the repository head.

## Required manual Railway settings audit

For **both** Railway services, verify in Railway before beta promotion:

- GitHub source repository is `adamtheballer/College-Football-Fantasy-App`.
- Branch is exactly `main`.
- Watch Paths are empty or include all release files for the service. In
  particular, do not exclude root-level `railway.api.toml`, `api/`,
  `scripts/`, `pyproject.toml`, or `uv.lock` from API releases.
- The lifecycle worker is not the only service triggered by a `main` merge.
- Automatic deploys are enabled, or the owner has an explicit release action
  for both services that records the target SHA.

Do not change these hosting settings from a code PR. Record and correct any
misconfiguration in Railway, then repeat the parity checks above.
