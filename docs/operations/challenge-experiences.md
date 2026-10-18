# Challenges expansion operations

## Architecture and compatibility

The Challenges tab and Home shortcut open `/weekly-challenges`. Four additional
modes reuse `WeeklyChallenge`, the canonical entry revision ledger, frozen game
and player snapshots, existing game facts, verified ESPN box scores, and CFFB
`points_from_verified_stats`. Existing five formats remain intact. Legacy clients
receive only those formats unless requesting `include_experiences=true`.

Raw Fan Points, fantasy points and survivor weeks are intentionally separate.
The existing overall championship continues its documented five-format awards;
new modes do not manufacture cross-mode achievement awards.

Migration `0125_challenge_experiences` follows `0124_release_notice`. It adds
normalized creator, salary, allegiance, survivor, decision and analytics facts,
foreign keys, per-account/competition uniqueness and indexed lookup keys. The
competition variant allows different creators or survivor series in one round.
Downgrade refuses when expanded competition data exists, preserving user history.

## Publish workflow

Admin: `/admin/challenge-experiences` (existing admin authorization). Select a
season/week, create the mode, configure a genuine scheduled slate, save, validate,
then publish with a review reason. Published slate identities, salaries, scoring,
school/conference metadata and creator branding are frozen. Every mutation checks
version/revision; a stale editor must reload. Hide/show preserves entries. The
existing five-format editor remains `/admin/weekly-challenges`.

- **Fan Wars:** choose supported Power Four schools from current CollegeTeam
  metadata. Allegiance is immutable within a competition week; future weeks do
  not rewrite it. Each game locks irreversibly at the earlier frozen/current
  kickoff or observed start. Default correct pick = 10 points. Accuracy uses
  total correct / resolved nonvoid eligible picks, with at least 3 distinct
  participating fans by default. Below-threshold schools are provisional.
  Fan Power sums earned points; thresholds and featured rivalries are editable
  before publication. Full precision determines ties before display rounding.
- **Fantasy Millionaire:** review one salary for every eligible pool player;
  a legal QB/RB/WR/WR/TE/FLEX formation must fit 100 virtual credits. Suggested
  salary v1 is `clamp(floor(0.8 * trusted published FINAL projection + 0.5),1,30)`.
  Missing trusted projections produce no suggestion; review is required. The
  immutable salary/scoring snapshot applies to every entrant. Global first
  kickoff lock; opposing lineups remain private beforehand. Verified zero and
  confirmed nonparticipation are distinct from missing facts (pending).
- **Beat the Creator:** register an approved, active profile; approve supplied
  logo and verified HTTPS links; select exactly 10 games and enter the creator's
  actual 10 approved picks before publication. Unapproved or incomplete profiles
  cannot publish. Correct pick = 10 points by default, with the same games and
  rules for creator and user. Picks reveal only after global lock. Corrections
  require an admin, reason, version and public disclosure. **Pigskin Dispatch's
  sponsorship does not authorize invented creator predictions. Keep its contest
  unpublished until those predictions are supplied and approved.**
- **Last Fan Standing:** create a separate series with explicit first lock and
  start/end weeks (Week 8 launch is supported). Publish each weekly slate; no
  registration after first lock, no team reuse or eliminated reentry. Official
  wins survive, losses and missed weekly picks eliminate. Uncertain games stay
  pending. Authorized void-and-advance and revocation require a documented
  decision; postponed games wait until the published window ends. Canceling a
  week advances registered users without inventing a prediction. Prior corrections
  reconcile later eligibility. Final-week surviving ties are joint winners.

Unpublished competitions are never offered for entry. Future-week previews stay
closed until the shared Matchup calendar rolls over. Historical records remain.
Actual scheduled games, player pool and reviewed prices must be provided each
week; a client update cannot invent or automatically approve them.

## Events, privacy and notifications

The existing lifecycle worker invokes settlement and reminder generation. Durable
notification delivery uses the existing outbox, quiet hours and user preferences.
Only published, enabled, real competitions with valid deadlines qualify. Reminder
expiry equals lock; result fingerprints prevent duplicate notifications and
supersede corrections. Challenge events send in-app/push only, never mass email.

Views/shares/referral opens are deduplicated per account and day, without IP or
cross-site fingerprints. Creator signup attribution is once per new account within
24 hours of signup. Optional analytics can be disabled per account and respects
browser DNT; entry/scoring still work. User deletion removes private event and
allegiance/enrollment facts; audited administrative decisions retain a null actor.

Sharing is user initiated. Before lock, lineup identities are concealed unless
explicitly included. Result cards use actual points/rank/best player. Universal
links support apex/www challenge routes and creator referral query parameters;
logged-out users continue after authentication; browsers provide the uninstalled
fallback. Entitlements and AASA must match the signed distribution profile.

## Deployment and verification

1. Run backend tests, PostgreSQL challenge/concurrency tests, migration upgrade /
   guarded downgrade / upgrade and metadata drift check, frontend tests,
   typecheck, browser mobile/desktop checks and production build.
2. Back up production using the existing private owner-only operational process.
3. Deploy combined API/workers with migration 0125 before publishing the new web
   bundle or installing a native package that consumes these endpoints.
4. Set `PLAYER_HEADSHOTS_ENABLED=false` and `LEAGUE_LOGOS_ENABLED=false` for the
   release until artwork permissions are confirmed. Stored URLs are preserved;
   responses omit portraits and league marks. User manager avatars, CFFB artwork
   and the approved week-specific sponsor remain available. Update store images
   to match. Do not claim content rights from a visibility flag alone.
5. Use actual admin data to configure/publish each mode. Existing five weekly
   competitions continue regardless of whether a new mode is published.
6. Inspect live authenticated `/weekly-challenges/current?include_experiences=true`,
   `/modes`, per-mode leaderboard and admin configuration. Verify worker SHA and
   migration revision. Never write test predictions to a real user's account.
7. Archive the canonical React bundle, verify signing, app/extension version,
   bundled-file parity, production API URL, push entitlements and universal links.
   Upload to App Store Connect only after release checks pass.

## Local validation evidence (October 17, 2026)

- Full backend: 1,309 passed, 7 skipped (proper PYTHONPATH and loopback access).
- Focused expanded modes: 39 passed, 1 PostgreSQL-only skip; the PostgreSQL
  run passed all 106 challenge tests, with 12 final history/concurrency/deletion
  cases rerun against PostgreSQL after refinements.
- Frontend: 690 tests across 103 files; application/test/Vite typechecks pass.
- Browser: 20 focused scenarios across 320/390/1280px, all four entry forms,
  signup/login return links, legacy formats/count limits and sponsor boundaries.
- Production Vite build passes. PostgreSQL migration preserves legacy records
  through upgrade/downgrade/upgrade, with no metadata drift.
- Interactive Chrome against the isolated real API saved all four official
  entries, verified the six-slot budget and disabled duplicate players, and
  exercised admin hide/show with audit preservation. No production test entries.

Screenshots are in the workspace artifact directory
`CFFB-builds/challenge-expansion-2026-10-17/` (outside this repository).
