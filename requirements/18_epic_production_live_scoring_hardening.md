# Production live-scoring hardening

GitHub issue: #68 — https://github.com/adamtheballer/College-Football-Fantasy-App/issues/68

## Purpose

Replace the legacy direct provider-to-mutable-score path with a fail-closed,
auditable scoring pipeline. This work must not enable public scoring during
beta. Public score, matchup, standing, and waiver priority read models remain
unchanged unless a later, separately approved promotion gate passes.

## Delivered foundation

- One canonical scoring engine is the only calculator used by immutable score
  snapshots.
- Provider payloads are captured as immutable raw events with hashes, request
  metadata, provider revision, and ingestion status.
- Player and game records require independently verified provider identities;
  no name, team, or position matching is used.
- Stat revisions are append-only, preserve missing fields as missing, and
  prohibit scoring until a provider marks a revision complete.
- Game lifecycle transitions are checked and corrections are written to an
  immutable correction ledger.
- League scoring rules are frozen per league-season in immutable policy
  snapshots.
- Score calculations are immutable and idempotent. Shadow mode records
  evidence but cannot update public scoring read models.
- Durable queue rows use idempotency keys, leases, retries, dead letters, and
  explicit worker ownership. The worker never polls a provider.
- The prior direct score synchronizer fails closed rather than fetching a
  provider or mutating legacy score tables.

## Still required before enabling scoring

1. Add a reviewed provider adapter backed by frozen fixtures and a separate
   authenticated ingestion process that writes only raw events.
2. Build deterministic public read-model promotion and rebuild tooling from
   immutable calculation snapshots, including standings, matchup, waiver, and
   historical correction reconciliation.
3. Add admin/operator views, SSE degraded-mode behavior, queue dashboards,
   alerts, replay tooling, and an operational runbook.
4. Complete shadow-mode reconciliation across representative full games,
   corrections, delays, provider outages, worker crashes, and restarts.
5. Obtain explicit release approval before switching `SCORING_MODE` from
   `disabled` or `shadow` to `enabled` and before deploying the scoring worker.

## Acceptance gates

- No provider response may be written directly to a mutable public score.
- No unknown identity, incomplete stat payload, duplicate ambiguity, or
  lifecycle violation may change a public score.
- Replay of the same events produces byte-for-byte equivalent immutable score
  calculations.
- Queue crash/retry/dead-letter behavior is observable and idempotent.
- Beta production configuration stays `SCORING_MODE=disabled`, does not deploy
  the scoring worker, and does not require provider credentials.
