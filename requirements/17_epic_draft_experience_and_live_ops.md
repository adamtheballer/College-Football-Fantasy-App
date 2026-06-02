# Epic: Draft Experience and Live Operations

## Summary

Deliver a production-ready fantasy draft and live operations system that combines:

1. ESPN-grade draft lifecycle and UX parity
2. Server-authoritative timeout autopick and timer progression
3. Transfer-aware player-card news quality controls
4. Live stats ingestion and league-scoring recompute
5. Push notification delivery with league-level preferences

This epic is the merged source of truth for:

- `17a_feature_draft_lobby_and_live_room_parity.md`
- `17b_feature_draft_timeout_runner_and_timer_authority.md`
- `17c_feature_player_card_transfer_aware_news_pipeline.md`
- `17d_feature_live_stats_scoring_and_realtime_sync.md`
- `17e_feature_push_alerts_and_notification_controls.md`
- `17f_feature_draft_flow_finalization_flex_and_wr_rank_corrections.md`

## Goals

- Make drafts reliable for 12+ managers in shared live rooms.
- Guarantee timer expiration always advances draft state without client polling.
- Remove misleading player-card news text and provide transfer-aware summaries.
- Provide near-real-time scoring updates driven by raw stat ingestion and league rules.
- Send actionable push alerts while honoring user and league preferences.

## Non-Goals

- Dynasty/keeper/offseason asset systems
- Native mobile app push (web/PWA push only in this phase)
- Full sportsbook-grade odds depth

## Delivery Model

Two-phase delivery:

1. Phase 1: Functional parity + reliability foundation
2. Phase 2: Advanced parity and premium polish

## GitHub Tracking

- Epic issue: **pending manual publish** (GitHub CLI unavailable in this environment).
- Child issues to publish and link back to these requirement docs:
  - `17a_feature_draft_lobby_and_live_room_parity.md`
  - `17b_feature_draft_timeout_runner_and_timer_authority.md`
  - `17c_feature_player_card_transfer_aware_news_pipeline.md`
  - `17d_feature_live_stats_scoring_and_realtime_sync.md`
  - `17e_feature_push_alerts_and_notification_controls.md`
  - `17f_feature_draft_flow_finalization_flex_and_wr_rank_corrections.md`

## Locked Defaults

- `web/` React is the canonical frontend.
- Snake draft only for this milestone.
- Total draft rounds are derived from configured roster slot totals.
- Pick timer is server-authoritative (90s clock + transition/prep windows).
- Timeout autopick selects top available player by ADP ordering.
- Player card tabs use explicit fallback states when data is missing.

## Release Gates

- No duplicate player ownership in a league.
- No blank critical panels after refresh/reconnect.
- No stuck drafts in 24h soak.
- Timer/on-clock/current-pick consistency across clients.
- Stable live scoring jobs without overlapping run conflicts.
- Push delivery obeys preference toggles.
