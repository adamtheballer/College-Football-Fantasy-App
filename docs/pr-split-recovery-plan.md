# PR Split Recovery Plan

Current branch: `feature/scoring-engine-v3`

Current state: this working tree contains too many unrelated milestones at once. Do not merge or push this tree as one branch.

## Rules

- Do not discard dirty files.
- Do not reset this branch unless the work is backed up first.
- Do not create one mega-PR.
- Create clean PR branches from updated `main`.
- Move one PR-sized slice at a time.
- Run tests for that PR before pushing.
- Keep operations work for PR 32–35 only.

## Safe Extraction Workflow

Use a clean worktree for each PR:

```bash
git fetch origin
git worktree add /private/tmp/cff-pr1 origin/main
cd /private/tmp/cff-pr1
git checkout -b codex/pr1-canonical-scoring-engine
```

Then copy only the intended files from the dirty worktree:

```bash
rsync -R \
  /Users/adambajdechi/Documents/Playground/api/app/domain/scoring_engine.py \
  /Users/adambajdechi/Documents/Playground/api/app/domain/scoring_rules.py \
  /Users/adambajdechi/Documents/Playground/api/app/domain/stat_normalization.py \
  /Users/adambajdechi/Documents/Playground/api/app/scoring.py \
  /Users/adambajdechi/Documents/Playground/api/app/services/scoring_service.py \
  /private/tmp/cff-pr1/
```

After copying, inspect diffs:

```bash
git status --short
git diff --stat
git diff --check
```

Only then run the PR-specific tests.

## Milestone A: Trust Core

### PR 1: Canonical Scoring Engine

Purpose: create one canonical scoring calculator for supported positions only: QB, RB, WR, TE, K.

Candidate files:

```text
api/app/domain/scoring_engine.py
api/app/domain/scoring_rules.py
api/app/domain/stat_normalization.py
api/app/scoring.py
api/app/services/scoring_service.py
tests/api/test_scoring_engine.py
```

Do not include:

```text
api/app/services/draft_service.py
api/app/services/trade_service.py
api/app/services/waiver_service.py
api/app/api/routes/admin_ops.py
web/client/pages/AdminScoring.tsx
```

Test command:

```bash
PYTHONPATH=. uv run pytest -q tests/api/test_scoring_engine.py
```

### PR 2: Scoring Settings Validation

Purpose: reject bad scoring rules before scoring runs.

Candidate files:

```text
api/app/domain/scoring_rules.py
api/app/core/config.py
tests/api/test_config.py
tests/api/test_scoring_engine.py
docs/scoring.md
```

Test command:

```bash
PYTHONPATH=. uv run pytest -q tests/api/test_config.py tests/api/test_scoring_engine.py
```

### PR 3: Golden Provider Scoring Fixtures

Purpose: make scoring deterministic against provider-like stat fixtures.

Candidate files:

```text
tests/fixtures/scoring/qb_week.json
tests/fixtures/scoring/rb_week.json
tests/fixtures/scoring/wr_week.json
tests/fixtures/scoring/te_week.json
tests/fixtures/scoring/k_week.json
tests/api/test_scoring_golden_fixtures.py
tests/api/test_scoring_engine.py
```

Do not include DST or IDP fixtures. This app does not use DST or IDP.

Test command:

```bash
PYTHONPATH=. uv run pytest -q tests/api/test_scoring_golden_fixtures.py tests/api/test_scoring_engine.py
```

### PR 4: Lineup Lock and Snapshot Correctness

Purpose: freeze player slots after kickoff and allow legal updates before kickoff.

Candidate files:

```text
api/app/services/lineup_locking.py
api/app/services/roster_legality.py
api/app/api/routes/rosters.py
api/app/models/lineup_week_snapshot.py
api/app/models/lineup_change_event.py
api/app/models/transaction.py
api/app/schemas/roster.py
api/app/schemas/transaction.py
api/alembic/versions/0034_roster_idempotency_lineup_events.py
tests/api/test_roster_workflows.py
tests/api/test_lineup_locking.py
```

Test command:

```bash
PYTHONPATH=. uv run pytest -q tests/api/test_roster_workflows.py tests/api/test_lineup_locking.py
```

### PR 5: Matchup Finalization and Stat Correction Versions

Purpose: make live/final/corrected score transitions explicit and auditable.

Candidate files:

```text
api/app/domain/matchup_state.py
api/app/services/matchup_finalization.py
api/app/services/matchup_scoring.py
api/app/services/stat_corrections.py
api/app/models/matchup_score_version.py
api/app/models/player_week_score.py
api/app/models/team_week_score.py
api/app/models/scoring_correction_audit.py
api/app/services/scoring_service.py
api/app/api/routes/admin_scoring.py
api/alembic/versions/0030_player_week_score_versions.py
api/alembic/versions/0032_matchup_score_versions.py
tests/api/test_live_scoring_recalc.py
tests/api/test_matchup_scoring.py
tests/api/test_stat_finalization_corrections.py
tests/api/test_stat_corrections.py
```

Test command:

```bash
PYTHONPATH=. uv run pytest -q tests/api/test_live_scoring_recalc.py tests/api/test_matchup_scoring.py tests/api/test_stat_finalization_corrections.py tests/api/test_stat_corrections.py
```

### PR 6: Standings Deterministic Recalculation

Purpose: standings update only from final/stat-corrected matchups and remain deterministic.

Candidate files:

```text
api/app/services/standings_recalc.py
api/app/services/scoring_service.py
api/app/models/standing.py
tests/api/test_standings_scoring.py
```

Test command:

```bash
PYTHONPATH=. uv run pytest -q tests/api/test_standings_scoring.py
```

## Hold Back: Milestone B and Later

These files should not be included in Milestone A PRs unless a specific Milestone A test proves they are required.

### League Lifecycle PRs 7–10

```text
api/alembic/versions/0029_audit_events.py
api/alembic/versions/0033_league_settings_versions_invite_controls.py
api/app/api/deps.py
api/app/api/routes/leagues.py
api/app/domain/league_lifecycle.py
api/app/domain/league_settings.py
api/app/domain/permissions.py
api/app/models/audit_event.py
api/app/models/league_invite.py
api/app/models/league_settings.py
api/app/models/league_settings_version.py
api/app/services/access_control.py
api/app/services/audit_service.py
api/app/services/league_flow.py
tests/api/test_audit_events.py
tests/api/test_authorization_matrix.py
tests/api/test_leagues.py
```

### Draft and Mock Draft PRs 11–14

```text
api/alembic/versions/0035_draft_clock_events_queue.py
api/alembic/versions/0036_mock_draft_queue_export.py
api/app/api/routes/mock_drafts.py
api/app/domain/draft_rules.py
api/app/models/draft.py
api/app/models/draft_event.py
api/app/models/draft_queue_entry.py
api/app/models/mock_draft.py
api/app/models/mock_draft_queue_entry.py
api/app/schemas/draft_room.py
api/app/schemas/mock_draft.py
api/app/services/autopick.py
api/app/services/draft_clock.py
api/app/services/draft_completion.py
api/app/services/draft_events.py
api/app/services/draft_service.py
api/app/services/mock_draft_service.py
tests/api/test_draft_room.py
tests/api/test_draft_race_conditions.py
tests/api/test_mock_drafts.py
web/client/pages/Draft.tsx
web/client/pages/DraftLobby.tsx
web/client/types/draft.ts
```

### Trades and Waivers PRs 16–21

```text
api/alembic/versions/0037_trade_offers_workflow.py
api/alembic/versions/0038_waiver_claims_engine.py
api/app/api/routes/trades.py
api/app/api/routes/waivers.py
api/app/models/trade_offer.py
api/app/models/trade_offer_item.py
api/app/models/trade_review.py
api/app/models/waiver_claim.py
api/app/models/waiver_priority.py
api/app/schemas/trade.py
api/app/schemas/waiver.py
api/app/services/trade_service.py
api/app/services/waiver_service.py
tests/api/test_trades.py
tests/api/test_trade_workflow.py
tests/api/test_waivers.py
tests/api/test_waiver_processing.py
web/client/pages/Trade.tsx
web/client/pages/LeagueWaivers.tsx
```

### Player Decision Tools PRs 22–26

```text
api/alembic/versions/0041_projection_metadata.py
api/alembic/versions/0042_injury_history_and_impact_metadata.py
api/alembic/versions/0043_watchlist_metadata_alerts.py
api/app/api/routes/injuries.py
api/app/api/routes/players.py
api/app/api/routes/projections.py
api/app/api/routes/stats.py
api/app/api/routes/watchlists.py
api/app/models/injury.py
api/app/models/injury_impact.py
api/app/models/projection_explanation.py
api/app/models/projection_input_audit.py
api/app/models/watchlist.py
api/app/models/weekly_projection.py
api/app/schemas/injury.py
api/app/schemas/player.py
api/app/schemas/projection.py
api/app/schemas/stats.py
api/app/schemas/watchlist.py
api/app/services/injury_impact.py
api/app/services/injury_normalization.py
api/app/services/injury_sync.py
api/app/services/player_availability.py
api/app/services/player_profile.py
api/app/services/player_search.py
api/app/services/projection_scoring_service.py
api/app/services/projections/engine.py
api/app/services/projections/explanations.py
api/app/services/projections/backtesting.py
api/app/services/projections/confidence.py
api/app/services/projections/snapshots.py
api/app/services/watchlist_alerts.py
api/app/services/watchlist_service.py
tests/api/test_injury_history_and_alerts.py
tests/api/test_player_pool.py
tests/api/test_projection_metadata.py
tests/api/test_watchlists.py
web/client/hooks/use-players.ts
web/client/hooks/use-watchlists.ts
web/client/pages/InjuryCenter.tsx
web/client/pages/LeagueWatchlist.tsx
web/client/pages/Stats.tsx
web/client/types/watchlist.ts
```

### Communication and UX PRs 27–31

```text
api/alembic/versions/0039_notification_delivery_state.py
api/alembic/versions/0040_league_chat.py
api/app/api/routes/chat.py
api/app/api/routes/notifications.py
api/app/models/league_message.py
api/app/models/notification.py
api/app/schemas/chat.py
api/app/schemas/notification.py
api/app/services/chat_service.py
api/app/services/notification_dedupe.py
api/app/services/notification_delivery.py
api/app/services/notification_service.py
tests/api/test_league_chat.py
tests/api/test_notifications.py
web/client/App.tsx
web/client/components/PageErrorBoundary.tsx
web/client/components/PageState.tsx
web/client/components/ProtectedRoute.tsx
web/client/components/league/LeagueTabs.tsx
web/client/components/league/RosterSlotTable.tsx
web/client/lib/api.ts
web/client/lib/api.spec.ts
web/client/lib/auth-events.ts
web/client/lib/leaguePreviewData.ts
web/client/lib/leagueState.ts
web/client/pages/LeagueInviteMembers.tsx
web/client/pages/LeagueMatchup.tsx
web/client/pages/LeagueRoster.tsx
web/client/pages/LeagueSettings.tsx
web/client/pages/Leagues.tsx
web/client/pages/Settings.tsx
web/client/types/league.ts
web/package.json
web/tests/e2e/auth.spec.ts
web/tests/e2e/core-workflows.spec.ts
web/tests/e2e/draft.spec.ts
web/tests/e2e/full-season.spec.ts
web/tests/e2e/trades-waivers.spec.ts
docs/frontend-ux.md
docs/testing-ci.md
```

### Production Operations PRs 32–35

```text
.github/workflows/ci.yml
api/app/api/routes/admin_ops.py
api/app/api/routes/admin_provider_sync.py
api/app/core/logging.py
api/app/main.py
api/app/middleware/request_telemetry.py
api/app/models/provider_sync_job.py
api/app/models/provider_sync_state.py
api/app/services/operations_metrics.py
api/app/services/provider_cache.py
api/app/services/provider_stats_service.py
api/app/services/provider_sync_jobs.py
api/app/services/readiness.py
api/app/services/sportsdata_sync.py
api/app/services/espn_stats_sync.py
api/alembic/versions/0031_provider_sync_jobs.py
tests/api/test_provider_identity_audit.py
tests/api/test_provider_sync_jobs.py
docs/operations-runbook.md
```

## Files That Need Manual Review Before Any PR

These files are shared across many milestones and likely contain mixed edits. Do not blindly copy them whole into a clean PR branch:

```text
api/app/main.py
api/app/api/deps.py
api/app/services/scoring_service.py
api/app/services/league_roster_matchup.py
api/app/services/notification_service.py
tests/conftest.py
web/client/App.tsx
web/client/pages/LeagueWaivers.tsx
web/client/hooks/use-players.ts
web/client/lib/api.ts
web/package.json
```

For these files, use hunk-level review:

```bash
git diff -- path/to/file
```

Then apply only the relevant hunks to the clean PR branch.

## Immediate Next Action

Start with PR 1 only:

```bash
git fetch origin
git worktree add /private/tmp/cff-pr1 origin/main
cd /private/tmp/cff-pr1
git checkout -b codex/pr1-canonical-scoring-engine
```

Copy only PR 1 files, run:

```bash
git diff --check
PYTHONPATH=. uv run pytest -q tests/api/test_scoring_engine.py
```

If PR 1 passes, commit and push that branch. Then repeat for PR 2.

