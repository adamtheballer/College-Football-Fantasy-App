# Feature: Draft Lobby and Live Room Parity

## Summary

Implement a dedicated pre-draft lobby and a fully functional live draft room with ESPN-style flow parity, while preserving the current product visual direction.

## Problem

- Lobby and draft room responsibilities are mixed.
- Draft timeline and on-clock status are not consistently modeled as explicit phases.
- Queue and roster experiences are not fully server-backed and deterministic.
- Live-room behavior can desync under reconnect and multi-user pressure.

## Scope

### Draft Lifecycle State Machine

- Add explicit phases: `filling`, `lobby_open`, `countdown`, `live`, `paused`, `complete`, `abandoned`.
- Persist and derive current pick, round, on-clock team, and completion from backend state only.
- Support transition and prep windows as first-class timing states.

### Pre-Draft Lobby

- Dedicated lobby route and API surface (not draft-room fallback).
- Show format/scoring/fill status/draft type/countdown.
- Support join/leave, slot movement before lock, and enter-draft gate.
- Commissioner controls: start now, pause, resume, cancel.

### Live Draft Room

- First-class tabs: `Players`, `Queue`, `Board`, `Rosters`.
- Header with centered timer, on-clock manager, and last-pick ticker.
- Pick carousel uses `round.pick` format and supports full-draft horizontal navigation.
- Board always derives from available players only.
- No board rank/index jump after picks; preserve scroll.
- Row actions are state-aware (`Queue`, `Draft`, disabled unavailable).
- Search/filter/sort by position/projection/ADP/value with reset affordance.

### Queue (Server-Backed)

- Persist queue per team+draft in backend.
- Support add/remove/clear/reorder.
- Autopick queue precedence when queue mode is enabled.
- Auto-prune drafted queue players via realtime updates.

### Rosters and Limits

- Team selector (`My Team`, `All Teams`).
- Render slots dynamically from league settings.
- Total rounds derived from slot count.
- Position-limits modal and fill status.
- Invariant: league waiver pool excludes league-rostered players.

### Walkthrough Overlay

- Draft tutorial steps with skip/next/progress.
- “Don’t show again” per user+league persistence.
- Never blocks critical on-clock actions.

### Player Card v1

- Open on player row/name click.
- Tabs: `Overview`, `News`, `Stats`, `Game Log`, `Projections`, `Odds`.
- Always render meaningful fallback state if tab data missing.
- Styling constraints: reduce intensity, smaller typography/icons, subtle school-color glow around player name only.

## Acceptance Criteria

- End-to-end 12-team draft runs from lobby to completion without stuck state.
- Queue operations survive refresh and reconnect.
- Board rankings stay stable after picks (no jump bug).
- Roster updates and ownership invariants hold for every pick.
- Walkthrough and player-card tabs render correctly on desktop/mobile.

## 2026-05-29 Delta: Lobby-First Flow + FLEX Precedence + WR Rank Diagnostics

### Added Requirements

- Draft flow from Home/Draft is lobby-first:
  - `Home -> Draft Tab -> Draft Lobby -> 90s Intermission -> Draft Start Visual -> Live Draft`.
- Lobby presence and readiness are realtime-visible:
  - `Join Draft Lobby` action.
  - `Ready` toggle and aggregate `Ready X / Y`.
  - Manager presence indicators: connected / idle / not joined.
- Intermission remains non-pickable:
  - Managers can inspect board/order/queue/rosters.
  - Picks remain disabled until live start visual completes.
- Timer authority remains backend-owned with phase contract:
  - `phase_type`, `phase_seconds_remaining`, `current_pick_timer_seconds`.
- FLEX precedence is strict:
  - RB/WR/TE overflow must fill FLEX before BENCH.
  - SUPERFLEX applies only when enabled.
- Sheet sync guardrail diagnostics must log WR rank checks:
  - Cam Coleman expected top-5 WR projection rank.
  - Ryan Williams expected top-10 WR projection rank.
  - Diagnostics log both projection-rank and ADP-rank snapshots.

### Additional Acceptance Criteria

- Clicking Draft from Home does not throw user directly into live picks.
- Lobby join/ready state updates replicate across connected clients.
- Auto-picks remain non-instant and follow pick transition cadence.
- FLEX slot is consumed before BENCH when eligible overflow occurs.
- Sheet sync output contains WR rank guardrail diagnostics for Cam/Ryan.
