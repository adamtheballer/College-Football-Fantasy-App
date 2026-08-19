# Live Scoring Game-Day Runbook

Use this runbook for each published scoring week. It is intentionally a
read-only operations checklist: the scoring worker remains the only process
allowed to promote provider totals into public matchup scores.

## Before lineups lock

1. In **Admin Scoring**, select the target season and week and open **Live
   Scoring Readiness**.
2. Do not publish a week unless **Public promotion** is **Ready**. Resolve every
   reported reason code first:
   - `SCORING_WORKER_UNHEALTHY`: restore the ESPN scoring worker and wait for a
     fresh healthy heartbeat.
   - `UNRESOLVED_STARTER_ESPN_ID`: verify the listed starter identity; do not
     map names manually from an ambiguous provider row.
   - `UNVERIFIED_ESPN_GAME_ID` or `UNAVAILABLE_ESPN_GAME`: correct the schedule
     mapping or move the matchup to a verified game window.
   - `UNSUPPORTED_LEAGUE_SCORING`: repair the affected league's scoring rules.
   - `PROVIDER_OUTAGE_OR_BLOCKED`: leave public scores unchanged and use the
     provider-outage procedure in `production-operations.md`.
3. Record the result of the read-only companion audit from the production worker
   environment:

   ```bash
   PYTHONPATH=. uv run python scripts/audit_espn_public_scoring_readiness.py --season 2026 --week 1
   ```

   Store the report with the release record. It must show no unresolved active
   starters, unsupported league scoring, blocked provider games, or unhealthy
   worker state.

## During the first live game

1. Watch **Live Scoring Readiness** through kickoff. The worker heartbeat must
   remain current and the accepted snapshot count must increase without 403,
   429, timeout, stale-ordering, or ambiguous-ordering alerts.
2. In a roster with a player in the game, verify these UI invariants after the
   first accepted in-game snapshot:
   - the main score is the current total, beginning at `0.0` at kickoff;
   - the pregame projection is secondary context below the total;
   - possession uses the neutral light treatment; red zone takes precedence;
   - final games stop showing a live projection.
3. Compare a sampled player total with the approved provider. If the provider
   response is partial, delayed, or regressive, do not manually zero a player;
   the worker preserves the last accepted snapshot by design.

## Live long-play alerts

Long-play alerts are opt-in and must be enabled only after the first live-game
check above succeeds. Set `LIVE_PLAYER_NOTIFICATIONS_ENABLED=true` in the ESPN
scoring-worker environment, then verify one in-app notification before
enabling external push delivery. Confirm the notification worker remains
healthy. The scoring worker queues an alert only when a newly
accepted provider play can be matched uniquely to a verified athlete in that
same box score; ambiguous names are skipped.

## After final

1. Confirm the game reaches final and run the postgame reconciliation worker.
2. Confirm matchup-final notifications only occur after certified finality.
3. Run the next-day correction sweep. If an official correction changes a
   result, use the Admin Scoring correction preview, verify every affected
   league, then apply it with an audit reason.

## Evidence required for alpha sign-off

- one pre-kickoff readiness report marked ready;
- one observed live game from kickoff through final;
- one sampled possession/red-zone UI check;
- one observed postgame reconciliation; and
- a review of worker, provider, and notification delivery alerts.

Do not mark live scoring fully certified until all five are recorded against
real provider data.
