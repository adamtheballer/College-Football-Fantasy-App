# Feature: Live Stats Scoring and Realtime Sync

## Summary

Provide near-real-time league updates by ingesting live player/game stats on schedule, converting stats to fantasy points using league scoring rules, and broadcasting deltas to connected clients.

## Problem

- Draft works in isolation, but live-week scoring and standings freshness are not fully operationally guaranteed.
- Provider fantasy points can diverge from league-specific scoring configurations.
- Without lock/retry controls, concurrent scoring jobs can overlap and corrupt trust.

## Scope

### Live Ingestion Pipeline

- Poll active-game stat feeds every 60 seconds.
- Poll injury feed every 120 seconds.
- Track provider freshness, run duration, and failure metrics.

### Scoring Conversion Engine

- Compute fantasy points from raw feed stats + league scoring rules.
- Do not use provider fantasy points as authoritative.
- Apply incremental recompute for:
  - player totals
  - team totals
  - matchup deltas
  - standings impact

### Realtime Fanout

Emit league-scoped events:

- `player.live.updated`
- `team.score.updated`
- `matchup.score.updated`
- `standings.updated`

Clients update views without full page reload.

### Reliability and Operations

- Lock scoring runs by league+week to prevent overlap.
- Retry with backoff; dead-letter failed cycles with diagnostics.
- Track `last_successful_sync_at` for every active league/week.

## Acceptance Criteria

- Live scoring updates appear within polling window targets.
- No overlapping scoring runs for same league/week.
- Realtime score events remain ordered and convergent after reconnect.
- Standings/matchups reflect recompute outputs deterministically.
