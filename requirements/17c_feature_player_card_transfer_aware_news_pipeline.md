# Feature: Player Card Transfer-Aware News Pipeline

## Summary

Replace brittle template-only “Latest News” generation with a deterministic source-priority pipeline that avoids misleading text and handles transfer context correctly.

## Problem

- Generic news generation can output nonsense for sparse/zero-stat rows.
- Transfer players need destination-aware context.
- Player cards need reliable metadata about news provenance.

## Scope

### Verified News Override Store

- Add persistent override store keyed by player+season:
  - `player_id`, `season`, `summary`, `is_transfer`, `from_school`, `to_school`, `expected_role`, `source_urls`, `verified_at`.
- Seed known transfer fixes (starting with Alonza Barnett III).

### Latest News Builder

Implement `build_player_latest_news(...)` with priority:

1. verified override
2. sheet-provided `latest_news` field (if present/non-empty)
3. stats-based generated summary (only when stats are meaningful)
4. neutral fallback context

Hard blocks:

- no “led offense” wording with zero-stat summaries
- no fabricated claims without source or meaningful stat context

### API Response Extensions

Extend season-summary response with:

- `latest_news_source_type` (`verified_override | sheet | generated_stats | fallback_context`)
- `latest_news_sources`
- `latest_news_verified_at`

Keep `latest_news` as backward-compatible text.

### UI Behavior

- Preserve existing latest-news card placement.
- Add optional source badge (`Verified`, `Sheet`, `Generated`, `Fallback`).
- Render transfer-aware messaging when applicable.

## Acceptance Criteria

- Transfer players show coherent transfer-aware summaries.
- Sparse-stat players never show nonsense “0-yard led offense” text.
- Source metadata is returned and displayed safely.
- Player card remains stable even when news data is missing.
