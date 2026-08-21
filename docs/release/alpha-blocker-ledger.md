# Alpha Final Certification Blocker Ledger

Certification started from `main` at `14a1a95f2eea6aeb84b25dc9d3d48fe817e81556` on 2026-08-21.

An entry is **VERIFIED** only when the named workflow completed against the
release candidate. A unit test alone is not sufficient for a production-like
claim. This file contains no production writes, migrations, or deploys.

| Priority | Feature | Root cause | Fix | Regression evidence | Status |
| --- | --- | --- | --- | --- | --- |
| P0 | Public legal routes | Hiding provider-disclosure navigation also removed its direct public route, violating the legal-page availability contract. | Restored `/provider-disclosure` as a public route without returning it to user-facing navigation. | `core-workflows.spec.ts`: direct public-policy route test passed; full browser E2E passed 25/25. | VERIFIED |
| P1 | Trade browser workflow | The test still asserted a retired linear “Analyze” flow after the approved roster → opponent → review builder replaced it. | Rewrote the E2E test to select each roster, review the trade, and assert the submitted payload. | Targeted trade E2E passed; full browser E2E passed 25/25. | VERIFIED |
| P0 | Live-scoring deployment contract | `deployments.yaml` still documented scoring as disabled and the scoring worker as omitted, while production runtime reports `SCORING_MODE=enabled` and expects provider polling. | Declared the explicit ESPN enabled mode, provider polling, durable scoring worker, and required live-scoring environment names. | `test_deployment_manifest.py`, config/health/worker/live-scoring regressions: 95 passed. | FIXED — pending final RC CI |
| P0 | Disposable PostgreSQL certification locally | Docker Desktop cannot read the local `postgres:16` image blob (`containerd … input/output error`), so a fresh local stack cannot start. | No application change is appropriate; restart Docker Desktop and re-pull the image. Do not purge Docker data without explicit approval. | Local `run_real_stack_e2e.sh` stops before application startup. GitHub-hosted checks remain the independent clean-environment evidence. | EXTERNAL BLOCKER |
| P0 | Fresh/upgrade/downgrade migration rehearsal | No local PostgreSQL is reachable after the Docker image-store failure. | Await healthy disposable PostgreSQL; then run fresh upgrade, upgrade-path, downgrade/re-upgrade, `alembic check`, API and all workers. | Static migration inventory has one head: `0103_sunday_waivers`; database parity cannot be claimed locally. | EXTERNAL BLOCKER |
| P0 | Full multi-user golden path | The repository has real-stack auth, draft and chat/trade E2E coverage, but no single five-user end-to-end scenario covering the complete 32-step release path. | Add/run the explicit golden-path suite in a healthy disposable stack. | Existing real-stack tests are intentionally separate and do not prove the full sequence. | OPEN |
| P0 | Live scoring operational replay | Unit/fixture coverage proves snapshot ordering, corrections, restarts, projections and final refreshes, but the full real worker pipeline must be replayed in a disposable PostgreSQL stack. | Run controlled fixture replay through API + ESPN worker after Docker recovery. | `test_espn_live_scoring.py`, `test_live_projection.py`, and `test_weekly_outlook_refresh.py` pass in unit scope. | OPEN |
| P1 | App Store/TestFlight path | Apple Developer Program enrollment is pending; Xcode cannot issue the required provisioning profile until Apple activates the membership. | Complete/await Apple enrollment; use the existing bundle identifier and TestFlight-test the native shell, photo picker and push registration. | Apple Developer account status shows Pending. | EXTERNAL BLOCKER |
| P1 | Real live-game observation | No official live game has occurred during certification. | Observe the first real game without seeding or mutating production data. | This is an operational verification, not a synthetic test substitute. | PENDING EXTERNAL GAME |

## Completed local evidence

- Backend: **789 passed** (14 deprecation/SQLAlchemy warnings).
- Frontend: typecheck passed; Vitest **320 passed** across 73 files; production build passed.
- Browser E2E: **25 passed, 3 skipped**. The skips are real-stack-only files, guarded by `REAL_STACK_E2E=1` and not assertion weakening.
- Focused deployment + live-scoring regression suite: **95 passed**.
- Candidate PR #161 before the final deployment-contract commit: CI verify, disposable PostgreSQL shadow stack, Docker clean boot, and real-stack E2E all passed. The candidate must be pushed and those checks must pass again after the new commit before certification can advance.

## External recovery steps

1. Quit and relaunch Docker Desktop.
2. Run `docker pull postgres:16`.
3. Re-run `COMPOSE_PROJECT_NAME=cff_alpha_rc ./scripts/run_real_stack_e2e.sh` and the migration/replay exercises against that disposable project.
4. Do not use Docker Desktop **Clean / Purge data** unless the owner explicitly approves its destructive effect.
