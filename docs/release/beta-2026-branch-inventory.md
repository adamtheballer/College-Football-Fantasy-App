# Beta 2026 Release Branch Inventory

Inventory date: 2026-07-26

Release candidate: `release/beta-2026-runtime` at the commit recorded immediately before the final PR.

This inventory is an ancestry classification, not a quality approval. A branch is included only when it is already an ancestor of the release candidate. Branches outside the candidate must not be merged into `main` for this beta without a separate review, conflict resolution, and validation pass.

## Already included in the release candidate

- `origin/codex/draft-order-active-marker`
- `origin/codex/fix-create-league-422`
- `origin/codex/fix-local-dev-port`
- `origin/codex/integrate-ready-core`
- `origin/codex/isolate-game-log-2026`
- `origin/codex/port-canonical-scoring-engine`
- `origin/codex/reconcile-canonical-0057`
- `origin/codex/reconcile-runtime-0075`
- `origin/codex/recover-canonical-0073`
- `origin/codex/restyle-create-league`
- `origin/codex/unified-waivers-v2`
- `origin/codex/waiver-wire-production-v2`
- `origin/feature/achitecture_cleanup`
- `origin/feature/scoring-engine`
- `origin/feature/trade-offer-lifecycle`
- `origin/hardening/fantasy-integrity-recovered`
- `origin/release/beta-integration`

## Explicitly excluded from this release candidate

These branches have commits not present in the candidate. They are not release-approved merely because they exist remotely.

- `origin/codex/fix-predraft-roster-placeholder-ui`
- `origin/codex/pr-split-recovery-plan`
- `origin/codex/remove-white-scrollbar`
- `origin/codex/scoring-milestone-a`
- `origin/codex/updated-code`
- `origin/codex/waiver-hardening`
- `origin/feature/create-join-league`
- `origin/feature/join-create-league`
- `origin/feature/matchup-test-branch`
- `origin/feature/mock-draft-lobby-multiplayer`
- `origin/feature/scoring-engine-v2`
- `origin/feature/scoring-engine-v3`
- `origin/feature/scoring-worker-hardening`
- `origin/feature/scoring-worker-reliability`
- `origin/feature/single-player-mock-draft-cleanup`
- `origin/hardening/fantasy-integrity`

## Working directories

Only `release/beta-2026-runtime` is the validated candidate. The other local worktrees at the time of the inventory point to `main` and are audit/reference worktrees, not integration sources.

Before publication, re-run:

```bash
git diff --check origin/main...HEAD
git status --short
git rev-list --left-right --count origin/main...HEAD
```

Then publish this branch, open the final PR to `main`, run the production gates in [the validation record](beta-2026-rc-validation.md), and merge only that reviewed commit.
