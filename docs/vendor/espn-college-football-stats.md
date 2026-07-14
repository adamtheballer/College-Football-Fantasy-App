# Vendored ESPN College Football Stats Reference

- Upstream repository: https://github.com/danabrey/espn-college-football-stats
- Pinned commit SHA: def7d08e8e91018106747675acad927a9c5955b3
- Pinned tag, if applicable: 2.1
- Retrieved on: 2026-07-12
- License: MIT, as declared in `composer.json` and README. The upstream snapshot does not include a standalone LICENSE file.
- Files used as implementation references:
  - `src/ESPNCollegeFootballStats.php`
  - `src/Extractor/PlayerStatsExtractor.php`
  - `src/Extractor/TeamStatsExtractor.php`
  - `src/PlayerSeason.php`
  - `tests/fixtures/jerry-jeudy.json`
  - `tests/fixtures/justin-herbert.json`
- Local modifications: None. The snapshot is vendored read-only under `vendor/espn-college-football-stats/`.
- Known limitations:
  - The upstream package is a PHP proof of concept around ESPN's undocumented JSON endpoints.
  - Pinning protects this application from upstream GitHub changes, but not from ESPN response-shape changes or ESPN restricting access.
  - The package maps player stat fields by category/index, not by explicit stat names, so this application uses the snapshot only as a reference and keeps parser validation in native Python.
  - Commercial or public use requires separate legal and provider-terms review.
- Implemented application contract:
  - ESPN historical imports are disabled by default with `ESPN_HISTORICAL_STATS_ENABLED=false`.
  - Player cards read only normalized cached rows by default and do not call ESPN during normal browsing.
  - The public endpoint is `GET /players/{player_id}/historical-stats`.
  - Provider refresh is not exposed through the player-card API.
  - One-time or scheduled imports run through `PYTHONPATH=. uv run python scripts/import_espn_historical_stats.py`.
  - Identity resolution prefers `player_provider_ids` rows for provider `espn`; legacy `players.external_id` is only a fallback.
  - Imported raw responses are hashed and stored in `provider_stat_cache`.
  - Normalized season rows are stored in `player_historical_season_stats`.
- Upgrade procedure:
  1. Review upstream changes manually.
  2. Pin a new exact commit SHA.
  3. Refresh `vendor/espn-college-football-stats/` from that commit.
  4. Update this document with commit, retrieval date, and parser-impact notes.
  5. Run historical parser fixtures and migration checks before enabling imports.
- Rollback procedure:
  1. Revert the vendor snapshot and parser changes to the prior known-good commit.
  2. Keep existing `provider_stat_cache` and `player_historical_season_stats` rows intact.
  3. Disable `ESPN_HISTORICAL_STATS_ENABLED` while investigating parser or provider failures.
