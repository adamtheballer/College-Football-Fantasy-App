# Issue #5 Checklist — SportsDataIO + DB Cache

- [x] Provider sync state table exists with feed/scope/expiry/status fields
- [x] SportsData feed reads are DB-first with stale-cache refresh behavior
- [x] Manual sync CLI exists for key feeds
- [x] Team/player/schedule/standings ingestion persisted in DB
- [x] Stats ingestion uses week-level/game-level bulk strategy
- [x] Injury ingestion preference/fallback path documented and implemented
- [x] `.env.example` contains no real API key values
- [x] Sync runs are idempotent and auditable
- [x] API surfaces data from DB snapshots, not direct provider passthrough
