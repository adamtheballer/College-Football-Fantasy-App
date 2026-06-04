# Feature: Draft Timeout Runner and Timer Authority

## Summary

Guarantee that when timer reaches `0`, the backend automatically commits an autopick for the on-clock team and advances draft state without requiring any client polling.

## Problem

- Timeout autopick currently depends on request-path evaluation.
- Draft progression can stall if no client calls room endpoints at expiry time.
- Multi-client/multi-worker conditions need idempotent timeout behavior.

## Scope

### Authoritative Timeout Runner

- Add background `draft_timeout_runner` started in app lifespan.
- Tick every 1s (configurable).
- Evaluate all live drafts and execute timeout picks where `seconds_remaining <= 0`.

### Canonical Timeout Pick Path

- Consolidate timeout autopick into shared service used by:
  - runner
  - request-time path (if retained as fallback)
- Use DB transaction + row locks.
- Use idempotency key `timeout:{draft_id}:{pick_number}`.
- Commit:
  - `DraftPick`
  - roster assignment
  - timer reset for next pick + transition/prep window
- Emit realtime events with reason `timeout_autopick`.

### Ranking Lock for Timeout Autopick

- Candidate query ordering:
  1. available only
  2. ADP ascending
  3. projection descending
  4. stable id ascending
- Never depend on client sorting state.

### Config + Ops

- Add flags:
  - `draft_timeout_runner_enabled`
  - `draft_timeout_runner_interval_ms`
- Add structured logs for timeout execution and outcomes.

## Acceptance Criteria

- Expired pick advances without client API calls.
- Duplicate timeout commits are impossible under repeated ticks.
- Next manager and timer always advance consistently.
- Realtime events are emitted for timeout picks and room updates.
