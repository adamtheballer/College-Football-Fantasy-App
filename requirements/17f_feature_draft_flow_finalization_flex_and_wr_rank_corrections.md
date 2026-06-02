# Feature: Draft Flow Finalization, FLEX Slot Precedence, and WR Rank Guardrails

## Summary

Finalize the draft user flow and data integrity rules for production draft testing:

1. Lobby-first entry from Home/Draft tab.
2. Two-stage server-authoritative countdowns (`60s lobby -> 90s intermission -> start visual -> live`).
3. Non-instant autopick pacing with uniform pick animation path for manual and timeout picks.
4. FLEX-before-BENCH slot assignment for RB/WR/TE overflow.
5. Google Sheet ranking integrity diagnostics for key WR guardrails (Cam Coleman, Ryan Williams).

## Scope

### Lobby-first Draft Flow

- Draft tab must route users into the draft lobby before live picks.
- Lobby must expose:
  - league + draft metadata,
  - manager list with connection status,
  - ready count and ready toggles,
  - draft order overview (snake direction visibility).
- Ready system is informational only for this phase and does not block timer-driven phase transitions.
- Lobby updates must be realtime-consistent across all connected clients.

### Intermission and Live Start

- On lobby timer expiry, transition all users into intermission state (90s).
- During intermission:
  - board/order/queue/rosters are viewable,
  - picks are disabled.
- At intermission 0:
  - show `DRAFT STARTING NOW` visual,
  - then enable Round 1 Pick 1.

### Autopick and Pick Animation Consistency

- Timeout autopicks remain backend-authoritative.
- Auto teams get a non-instant on-clock window (`~3s`) before commit.
- Every committed pick (manual or timeout) must follow the same event path so the UI animation always triggers.

### FLEX Overflow Rule

- Slot assignment order must be:
  - primary position,
  - FLEX (RB/WR/TE),
  - SUPERFLEX (if enabled),
  - BENCH,
  - IR.
- Position normalization must handle depth labels (`WR1`, `RB2`, etc.) before assignment.

### Sheet Ranking Guardrails

- Google Sheet remains source of truth for projections/ranking inputs.
- Sync pipeline must log WR guardrail diagnostics:
  - Cam Coleman projection rank target: top-5 WR.
  - Ryan Williams projection rank target: top-10 WR.
- Diagnostics must include:
  - projection-rank,
  - ADP-rank,
  - top WR snapshot.

## API and Event Requirements

- Lobby actions:
  - `POST /leagues/{league_id}/draft-room/lobby/join`
  - `POST /leagues/{league_id}/draft-room/lobby/ready`
  - `POST /leagues/{league_id}/draft-room/lobby/heartbeat`
- Draft room payload must include:
  - `phase_type`
  - `phase_seconds_remaining`
  - `current_pick_timer_seconds`
  - per-team lobby flags (`joined`, `connected`, `ready`)
  - lobby aggregates (`joined_count`, `connected_count`, `ready_count`)
- Realtime events must include lobby/draft status transitions and pick reasons.

## Acceptance Criteria

1. Home -> Draft opens lobby flow, not direct live picks.
2. Lobby join and ready states replicate live to all clients.
3. `scheduled(60s) -> countdown(90s) -> live` transitions run server-authoritatively.
4. Timeout autopicks are non-instant and committed once.
5. Pick animations trigger for every pick path.
6. RB/WR/TE overflow fills FLEX before BENCH.
7. Sheet sync logs WR guardrail diagnostics (Cam/Ryan ranks + top WR list).

## Tracking

- This file is the source of truth for the finalization delta.
- Matching GitHub epic/story issues must reference this file and `requirements/17a_feature_draft_lobby_and_live_room_parity.md`.
