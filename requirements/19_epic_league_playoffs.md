# Epic: Canonical League Playoffs

## Summary

Add a complete, multi-season College Football Fantasy postseason that uses the
existing canonical `matchups` table, weekly scoring, player locks, live scoring,
and matchup presentation. A postseason record only supplies bracket topology,
seed snapshots, routing, audit state, and final placements; it must never own a
second scoring path.

## Product Rules

- Supported playoff team counts are exactly `2`, `4`, `6`, and `8`, never more
  than the league's team count.
- The season calendar is derived only from a versioned, sealed schedule
  artifact—not an imported database row, mutable Sheet, or live provider
  response. Its eligible universe is ACC, Big Ten, Big 12, SEC, and Notre
  Dame. The calendar accepts only contiguous weeks where every eligible school
  has one verified non-BYE regular game; it excludes cancelled,
  conference-championship, bowl, and CFP rows and fails closed on missing or
  contradictory evidence.
- For the approved 2026 policy: two-team championships use Week 13; four-team
  playoffs use Weeks 12–13; six- and eight-team playoffs use Weeks 11–13.
  The derived calendar is snapshotted with its policy version, source identity,
  revision, SHA-256, and format version when a league plan is created. Existing
  leagues are never silently rewritten, and started/final matchups are never
  deleted.
- Seeding uses the canonical regular-season standings snapshot: win percentage,
  points for, unambiguous head-to-head, lower points against, then a persisted
  audited deterministic draw. Seeds lock only after every required regular
  season matchup is final/corrected.

### Postseason history and schema invariants

- A permanent bracket is unique by `(league_id, season)`. New final-standing
  writes always have a valid `bracket_id` and are unique by both
  `(bracket_id, team_id)` and `(bracket_id, final_place)`.
- Pre-canonical historical rows may have nullable `bracket_id`. Their legacy
  `(league_id, season, team_id)` and `(league_id, season, final_place)` unique
  constraints remain intentionally so PostgreSQL's nullable unique semantics
  cannot permit duplicate unlinked history.
- Migration readiness, CI, Docker boot, real-stack E2E, and shadow
  certification derive the one repository Alembic head dynamically; none may
  hardcode an expected revision.
- League postseason snapshots preserve regular-season start/end,
  playoff/championship weeks, round count, calendar policy version, and sealed
  schedule provenance so historical season results remain reproducible.
- Seeds may rebuild before the first playoff kickoff after a regular-season
  correction; after kickoff, the field and seed order are immutable.
- Exact final-score playoff ties advance the higher original seed under the
  server-visible `HIGHER_SEED_V1` policy.
- Higher seed is the deterministic home team. This is not a scoring advantage.
- A bye is a bracket result only, never a `0.0 vs 0.0` canonical matchup and
  never a win/loss.
- Matchups are materialized only when both teams are known, with one linked
  canonical `Matchup` per postseason node.
- Bracket advancement and notification delivery must be transactionally
  idempotent and safe under duplicate worker observation.
- An official stat correction before a dependent matchup starts may repair that
  future node. Once a dependent matchup has started, conflicting correction
  enters `REVIEW_REQUIRED`; it must not silently replace a live participant.
- A championship correction recalculates champion, runner-up, final standings,
  and career results when no downstream competitive game depends on it.

## Bracket Formats

- **2 teams:** #1 vs #2 championship.
- **4 teams:** #1/#4 and #2/#3 semifinals; winners play championship and losers
  play third place.
- **6 teams:** #1/#2 receive first-round byes; #3/#6 and #4/#5 quarterfinals;
  #1 faces the #4/#5 winner and #2 faces the #3/#6 winner; quarterfinal losers
  play fifth place; semifinal winners play championship and semifinal losers
  play third place.
- **8 teams:** #1/#8, #4/#5, #2/#7, #3/#6 quarterfinals; winners progress to
  title semifinals and losers to placement semifinals; title and placement
  paths determine 1st through 8th.

## Lifecycle, Standing, and History

- Lifecycle states: `PLANNED`, `SEEDING_PENDING`, `LOCKED`, `ACTIVE`,
  `FINALIZING`, `COMPLETED`, and `REVIEW_REQUIRED`.
- The existing lifecycle worker advances postseason state and processes
  finalized canonical playoff matchups. No extra polling worker or direct
  provider integration is permitted.
- Regular-season standings must not count postseason games. Final standings
  assign every playoff team its bracket placement and place non-qualifiers in
  locked regular-season order behind them.
- The final result is historical and multi-season: one league supports separate
  2026, 2027, and later brackets without overwriting old data.
- Locked seeds and completed placement results are the only source for career
  playoff appearances, championship appearances, championships, runner-up,
  third-place, top-three, and postseason W/L aggregation.

## API and Authorization

- Authenticated league members may read `GET /leagues/{league_id}/postseason`
  and `GET /leagues/{league_id}/postseason/bracket`.
- The regular-season response is an explicitly non-persisted “if the season
  ended today” preview. The bracket response contains seeds, nodes, routing,
  linked canonical scores/statuses, and final standings in one bulk-loaded
  response.
- No commissioner or normal-user endpoint can set a winner or champion.
- All error, empty, loading, authorization, and review-required states must be
  explicit in the API contract and React client.

## UI

- Post-draft league navigation includes **Playoffs**.
- During regular season it shows a compact **Playoff Picture** with an explicit
  playoff-cut line and no unproven clinched/eliminated labels.
- During postseason it shows a mobile vertical, round-by-round bracket and a
  desktop column layout. Cards reuse canonical matchup scores/projections,
  show seeds, manager avatar/name, team, state, and winner, and link to the
  ordinary matchup page.
- Six-team byes are rendered as byes, not empty matchup cards. Placement and
  final standing views stay distinct from championship routing.
- League settings and the postseason view show the derived regular-season end,
  playoff start, championship week, round count, higher-seed tie rule, and a
  clear lock explanation. The format can regenerate only before the first
  regular-season matchup starts.
- Matchup pages render server-derived postseason context; championship receives
  an original app-owned gold treatment. Existing rivalry context may coexist but
  cannot alter postseason scoring.

## Safety and Operations

- Add a dry-run-first `scripts/audit_postseason_readiness.py`; mutations require
  `--apply` and may not delete started/final matchups.
- Add `scripts/certify_season_calendar.py`, which produces JSON and Markdown
  evidence from the sealed source and blocks release when the source or full
  coverage proof is unavailable.
- Add structured, identifier-only lifecycle events and deterministic
  notification keys for seeds, bye, matchup, advance, and champion events.
- Add migration safety tests: current-head upgrade, downgrade, upgrade, fresh
  database-to-head, and exactly one Alembic head.
- Development must not write to, migrate, or deploy production.

## Acceptance Criteria

- All four bracket formats, normal/placement routing, final standings,
  multi-season history, canonical live scoring, player locks, win probability,
  tie policy, corrections, and idempotency are covered by database and
  real-stack tests.
- The playoff page has preview, pending, active, completed, review-required,
  loading, and failure states; it is readable on 320px through desktop screens
  with no document horizontal overflow.
- Existing regular-season league creation, draft, roster, matchup, waiver,
  trade, live score, rivalry, and career flows remain covered by regression.

## Tracking

The matching GitHub epic must reference this file. Delivery is a single feature
branch and pull request; it must not merge or deploy automatically.
