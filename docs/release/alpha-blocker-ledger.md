# Alpha Final-Hardening Blocker Ledger

Baseline: `48153f7f9854efc27095d52d0efe629d751f8789` (`main`)

This ledger is intentionally evidence-driven. An item is **VERIFIED** only after
the associated workflow has passed; a passing compile or unit test alone is
not sufficient.

| Priority | System | Problem | Root Cause | Fix | Test | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Baseline / release integrity | Final alpha baseline, open PRs, migrations, runtime flags, and deployment configuration required a combined audit. | Release work landed through several feature PRs. | Audited `48153f7`, excluded every stale/unsafe open PR, and validated one Alembic head plus clean migration downgrade/re-upgrade. | Git/PR/config/Alembic inventory; disposable PostgreSQL migration test. | VERIFIED |
| P0 | Real multiplayer draft | End-to-end concurrent draft behavior must be revalidated from the current main baseline. | High-integrity workflow; prior tests alone are not release evidence. | No defect found. | Real stack: signed-in two-manager timeout/auto-pick lifecycle passed; full backend suite passed. | VERIFIED |
| P0 | Player locking / roster integrity | Kickoff-boundary and direct-request enforcement must be verified against canonical kickoff timestamps. | A UI restriction is insufficient without server authority. | No defect found. | `test_player_lock_service.py` plus full backend suite: 706 passed. | VERIFIED |
| P0 | Waivers / trades / scoring | Cross-user mutations and scoring idempotency require final integrity verification. | These workflows alter canonical league state. | No defect found. | Targeted scoring/waiver/trade suite: 185 passed; real stack private-chat/trade isolation passed. | VERIFIED |
| P1 | Auth / manager profile | Session lifecycle and avatar propagation need current-build regression verification. | Past profile-photo fixes touched cache and client state. | Hardened unsafe post-login redirect. | Auth session tests, Login unit regressions, full frontend suite (304), and real-stack signup/session workflow passed. | VERIFIED |
| P1 | Official availability | Daily P4 import and player/alert propagation need source, idempotency, and schedule verification. | Provider availability depends on official reports and production data timing. | No local defect found. | Official-report parser/import tests passed in the targeted 185-test suite and full backend suite. | VERIFIED |
| P1 | Mobile / navigation / error states | Required alpha routes need viewport and browser-console coverage. | Prior UI work spanned several independent routes. | No local defect found. | 24 browser E2E passed (3 intentional real-stack-only skips); full frontend suite passed. | VERIFIED |
| P2 | Auth redirect safety | Login trusted arbitrary browser history state as a post-login destination. | The value was not constrained to a same-app path. | Reject absolute, protocol-relative, and backslash paths; preserve only same-app destinations. | `Login.spec.ts`: 10 passed; full frontend suite: 304 passed; typecheck/build passed. | VERIFIED |
| External | App Store compliance | Public privacy policy, terms, and data-provider disclosure URLs are unset in production. | Owner-controlled legal content and hosting are not present. | Await owner-provided approved URLs. | Production runtime health confirms URLs. | EXTERNAL BLOCKER |
| External | Production data verification | A real official availability report and live game feed must be observed after their providers publish. | Cannot manufacture provider data or a live game. | Monitor scheduled run and live operational data after availability. | Production operational smoke test. | EXTERNAL BLOCKER |
| P2 | Development dependency advisories | `npm audit` reports five development-only advisories through test/build tooling. | Upstream dependency chain includes non-breaking patch gaps and a React Router major-version upgrade path. | No alpha runtime dependency advisory exists; defer major dependency upgrade to a separate post-alpha compatibility PR. | `npm audit --omit=dev --json`: 0 production advisories. | DEFERRED |

## Final local evidence

- Backend: **706 passed** in 58.45s.
- Focused P0 backend workflows: **185 passed** in 24.38s.
- Frontend unit/component: **304 passed** across 69 files.
- Browser E2E: **24 passed**, with **3 intentional real-stack-only skips**.
- Docker Compose clean boot + real-stack browser workflows: **3 passed** (signup/session, two-manager draft lifecycle, private chat/trade isolation).
- Frontend typecheck and production build: passed.
- Production dependency audit: **0 vulnerabilities**.
