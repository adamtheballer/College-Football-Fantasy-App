# Weekly Challenges — local combined-build implementation

This feature is local and unreleased. Migration `0123_weekly_challenges` is prepared;
no production migration, deployment, push, merge, native sync/build, or App Store/
TestFlight upload is authorized by this feature request. Prior notification/review
rollout notes describe the earlier release, not deployment of Weekly Challenges.

## Product and integration

Home links to `/weekly-challenges`, with a separate leaderboard action. No sidebar
or bottom-navigation destination was added. Existing Pick 6 archives remain intact;
the retired Home promotion is not restored. The hub contains exactly five formats:
Slate 12, Upset Hunter, Fantasy Five, Lock of the Week and Rivalry Duels.
All entries are free. Recognition is cosmetic, with no cash, transferable or
redeemable value. Season Championship is the accumulated finalized awards view,
not another entry. Membership, subscriptions and payment integrations are unchanged.

The app uses React/React Query, FastAPI, verified JWT account IDs, SQLAlchemy and
PostgreSQL. New models reference existing `users`, `games` and `players` tables.
`weekly_challenges.py` owns transactions and domain rules; thin API routes declare
Pydantic contracts. API/session refresh is shared with existing app calls. Browser
writes carry an account precondition through token refresh, so an old account's
form cannot mutate a newly signed-in account's entry.

There was no public manager-profile route or app-wide user-discovery route in the
repository. `/managers/:userId` adds the minimal profile destination using existing
public name/username/avatar fields and `ManagerAvatar`. It exposes no email,
contact information, account security data, or private league roster. Duel discovery
uses the same public fields. Existing league-specific chat/invitation flows remain
unchanged.

## Actual weekly calendar

`league_weeks.py` is the authority. Operational scoring/waiver weeks reset Tuesday
at 08:00 America/New_York. Home/Matchup presentation retains the previous matchup
through Tuesday, then advances at Wednesday 00:00 Eastern. The review-window policy
and DST-safe boundary function are now shared with app-wide challenge rounds.
League-specific fallback selection is preserved; challenges do not choose an
arbitrary user's league or create synthetic Matchup/League rows.
The shared review offset applies only after Tuesday's 08:00 operational reset;
before that reset the calendar already names the old week. Regression coverage
prevents the previous extra backward step during Tuesday's first eight hours.

The canonical display cursor supplies the current season/week. The existing
lifecycle worker ensures the new round and its five Upcoming drafts; `/current`
can also safely initialize the same unique round. A unique constraint prevents
parallel initialization from making duplicate rounds. A new round never copies
last week's games, entries or scores. Admins can prepare and publish a future
round in advance; it remains Upcoming until the canonical cursor reaches it.
Unpublished or expired slates never open. The existing regular-season cursor
clamps to week 15; advancing the configured season remains the existing app's
season-administration responsibility.

Saturday results do not advance this cursor. Old rounds stay Closed and retain
entries and results through the review period. Old-week settlement is scoped by
challenge/round IDs and cannot overwrite the current week. There is no new Wednesday
cron or client week-reset timer.

## Publishing and deadlines

Use the Home hub's **Manage Challenges** link as an administrator:

1. Load/prepare a season and week. The catalog reads that week's canonical games
   and the existing approved draft/waiver Power 4 plus Notre Dame player pool; historical/provider-only records and ambiguous player/game mappings
   are excluded. No games, underdogs, difficulty values or player facts are invented.
2. Select the complete game slate. Slate 12 requires exactly 12 distinct games and
   a featured tiebreaker; Rivalry Duels requires five common games. Upset Hunter
   requires explicit underdog designation and fixed difficulty 1–5 for at least
   three distinct games; each published game needs its designated underdog. No odds formula or paid provider is added.
3. Fantasy Five needs a published player pool that can fill QB/RB/WR/TE/FLEX with
   distinct canonical players in the selected games. Every published game must
   supply an eligible player, so invisible/unselectable games cannot set a
   deadline or prevent no-contest treatment. It freezes existing
   `get_scoring_rules()` and `CALCULATION_VERSION`, not a selected league's rules.
   Missing/invalid canonical scoring configuration blocks publication.
4. Save, validate, then publish the saved configuration with an audit reason.
   Publication freezes IDs, identity snapshots, rules, weights and scoring config.
   Published configurations cannot be replaced; cancel instead.

The shared UTC deadline is earliest published kickoff minus five minutes. Later
schedule changes cannot extend/reopen it; an earlier verified kickoff can shorten
it. A sourced started/final game closes entry even if its timestamp is wrong.
Pregame delays alone do not prematurely close a still-future slate. A persisted
close cannot be undone by reload, restart or a later schedule repair. The entire
challenge shares the cutoff, regardless of a user's selected games or players.

Every entry/invitation mutation locks the challenge row, then reads server time.
At the deadline or later it rejects the mutation. A second cutoff check precedes
commit. Rejection rolls back any partial edit and persists only the irreversible
close. Client state uses a server-anchored deadline timer for presentation; device
clock changes never authorize a write. Request failures preserve account/round-
scoped unsaved choices in session storage where available.

One official entry is enforced by `(challenge_id,user_id)` uniqueness. Expected
revision prevents stale overwrites. Incomplete drafts may be saved before official
submission. After submission, changing ranked picks requires **Update Official
Entry**; Save Draft cannot silently replace an official entry.

Both duel participants need complete official entries before acceptance. A unique
`(challenge_id,user_id)` seat record covers inviter and invitee roles, with both
seats committed in the same transaction. Self/duplicate pairs and foreign responses
are rejected. Unaccepted/incomplete invitations award no automatic win. Opponent
choices remain hidden until the shared deadline.

## Settlement and corrections

`run_lifecycle_worker.py` calls the shared settlement service, internally limited
to due checks every 60 seconds per challenge with row locking/skip-locked claims.
No new provider, scheduler process or per-player network polling is introduced.
The service batches game/player facts and ranks the full submitted field.

- Winner formats use authoritative `Game` status and final scores. Non-null live
  scores or elapsed Saturday time never imply finality.
- Fantasy Five uses game-bound `PlayerGameStat` facts from the existing accepted
  final-box-score source and the canonical CFFB engine with frozen rules. Raw
  totals are separate from placement awards. Unknown engine versions block finality.
- Confirmed zero box scores remain real zeros. A missing row remains Processing.
  Existing sourced, reviewed effective OUT/SUSPENDED/INELIGIBLE/season absence
  assertions can establish a final zero for a nonparticipant after game finality.
  Newer FULL reports clear older OUT assertions. The existing Pick 6 reader shares
  this effective-absence helper rather than keeping duplicate selection logic.
- Canceled games are void. Delays remain pending. Postponements past the next
  canonical rollover are void, as are unresolved explicitly postponed games once
  that rollover passes. Ordinary unfinished delayed games are not finalized by
  Saturday night or the calendar alone. Rollover voids are retained in the
  immutable settlement ledger; a later final response cannot resurrect those picks.
- All relevant slate games void means no contest: zero awards and no winner badges.
  Voiding the Slate 12 featured game disables the tiebreaker for everyone.

Final scores and current awards each have one database row per entry. Source hashes
cover frozen config, game identity/results, selected entry revisions/choices,
accepted duels, box-score facts and confirmed absences. A repeat job with identical
inputs is a no-op. Corrections recalculate the entire affected field, including
Fantasy Five competition ranks (1,2,2,4). Updating one award row replaces points;
it never appends a second award. Withdrawing finality or invalidating game identity
withdraws prior points and badges until the source is trustworthy again. Audit
rows retain prior/new awards, reasons and source snapshots. No client submits
winners, raw scores or points.

Weekly and season leaderboards rank the entire eligible population using a database
window function before limiting to ten rows. Ties share rank; user ID provides only
stable display order. A separate Your Rank row covers an entrant outside the Top
10. Season totals exclude unfinalized challenges; weekly views label partial
standings Provisional. A distinct Your Result summary is returned independently
of result-page pagination. Per-challenge winners receive cosmetic recognition;
overall weekly-winner badges appear only once all five instances are final,
no-contest or canceled. Corrections revoke obsolete recognition without erasing
the audit trail.

## API and error contract

Public authenticated prefix `/weekly-challenges`:

- `GET /current`, `/rounds/{id}`, `/history?limit=15&offset=0`.
- `GET /challenges/{id}` and `/challenges/{id}/entry` (caller only).
- `PUT /challenges/{id}/entry` with expected revision, submit flag, selections and
  the Slate 12 tiebreaker. Format-specific extra fields are rejected.
- `GET/POST /challenges/{id}/duels`; `POST .../duels/{id}/accept|decline`.
- `GET /challenges/{id}/results?limit=25&offset=0` (bounded at 100, includes own result).
- `GET /leaderboard?season=...&round_id=...` for weekly; omit round for season.
- `GET /participants?q=...` (20 public matches), `/participants/{id}`.

Admin prefix `/admin/weekly-challenges`:

- `POST /rounds/{season}/{week}`, `GET /catalog?season=...&week=...`.
- `GET/PUT /challenges/{id}` for draft configuration with expected version.
- `POST /challenges/{id}/validate|publish|cancel|score|correct`.
- `GET /challenges/{id}/audit?limit=25&offset=0`.

Mutation limits reuse the existing persisted rate limiter (60 attempts/account/minute,
including rejected requests). Authentication/administrator dependencies remain the
existing ones. Ownership comes from the verified account; a client account header
is only a stale-session precondition. Domain errors use `detail` objects with
`code`, `message`, challenge/round IDs and current deadline where available:
`DEADLINE_PASSED`, `CHALLENGE_CLOSED`, `NOT_PUBLISHED`, `INVALID_ENTRY`,
`INCOMPLETE_ENTRY`, `DUPLICATE_DUEL`, `UNAUTHORIZED`, `VERSION_CONFLICT`,
`INVALID_CONFIGURATION`, `IMMUTABLE_RULES`, `TEMPORARY_DATA_FAILURE`.
Standard FastAPI authentication and request-validation errors retain their existing
401/403/422 contracts. Admin draft fields are normalized by `SlateConfig`; ordinary
readers get no unpublished games, players, underdogs or draft configuration.

Bruno examples are under `bruno/collections/backend-api/WeeklyChallenges`.
SaveEntry/Configure examples use Lock of the Week; obtain real IDs and revisions
from authenticated responses. Do not run them against production until the
combined release is approved.

## Migration and local verification

`0123_weekly_challenges` is additive and follows 0122. Canonical master tables and
historical Pick 6 rows are untouched. Account foreign keys follow existing cascade
behavior; deleting an account does not leave the old account publicly ranked.
Downgrade is allowed only before any challenge round exists, so release rollback
cannot silently erase published rules, entries, awards or audit history.

The migration was generated against a disposable PostgreSQL 18 database upgraded
to 0122, reviewed, and exercised through upgrade/check/downgrade/re-upgrade/check.
An isolated browser preview uses local ports 18457 (API) and 18458 (React), with
email, push, provider polling and App Review disabled. It is the working tree,
not a deployed release. `scripts/seed_weekly_challenges_dev.py` refuses production,
remote hosts and database names outside the dedicated `cff_challenges_*` namespace.
Fixtures and test accounts never create production entrants or winners.

Detailed final test counts and browser evidence belong in the New Build checklist.
No standalone repository lint task is configured; TypeScript, tests, web build,
migration parity and `git diff --check` are the available checks.

## Combined-release prerequisites

Keep the feature local until explicit combined release approval. Then back up the
production database, apply 0123 before starting the new API/lifecycle worker,
ship the matching React bundle in the eventual approved iOS build, and configure/
validate/publish the real current and next-week slates. No native build, sync,
App Store upload or production changes were performed for this feature.

Actual source/configuration prerequisites: sufficient verified future games for
Slate 12/duels, an eligible five-slot player pool, and explicit admin underdogs and
difficulty values. Incomplete inputs remain Upcoming or block publishing. Historical
or missing box scores remain Processing; no source facts are fabricated to finish
settlement. Distribution-device verification awaits the combined native build.

## Changed files and verification entry points

| Area | Files / reused integration |
| --- | --- |
| Persistence | `api/app/models/weekly_challenge.py`, additive migration `0123_weekly_challenges.py`, existing model registry |
| API | `api/app/schemas/weekly_challenge.py`, `api/app/api/routes/weekly_challenges.py`, existing `main.py` routers/auth/rate limiter |
| Lifecycle and scoring | `api/app/services/weekly_challenges.py`, existing lifecycle worker, canonical game selection/player filters/scoring engine, shared `league_weeks.py` and effective injury status helper |
| React | `WeeklyChallengesHome`, shared challenge hook/types, hub/detail/leaderboard/admin/profile pages; existing app routes, Home and API refresh |
| Verification | `tests/api/test_weekly_challenges.py`, calendar/lifecycle regressions, entry/Home/API frontend tests, 19 Bruno requests, guarded local fixture script |

The full-suite beta reconciliation test had an unrelated wall-clock fixture that
could expire between collection and execution. Its test-only clock is now fixed;
production beta logic is unchanged. This makes the expanded full-suite run
repeatable rather than extending a real-time reservation timeout.

Browser verification used actual local API/database responses, including an
administrator publishing Lock of the Week, both managers' duel acceptance,
server-confirmed submissions, deadline rejection, authoritative missing-stat
processing, final scoring and repeated corrected scoring. Desktop and mobile
layouts were inspected; physical-device testing was not performed. Controlled
fixture awards changed from 23/15 to 21/10 after correction with exactly six award
rows throughout. The screenshots show test accounts and synthetic game outcomes.

Final verification: full backend **1,218 passed / 5 skipped**, full frontend
**636 passed in 98 files**, and dedicated PostgreSQL 18 challenge/calendar tests
**64 passed with no skips**. PostgreSQL covers both concurrency cases skipped on
SQLite. App/test/Vite TypeScript checks, Vite build, local readiness, migration
parity and staged/working-tree diff checks passed. Nineteen Bruno examples are
prepared; the Bruno CLI is not installed, so collection execution was not claimed.
Logs are local `/private/tmp/cff-weekly-challenges-*.log` artifacts, not deployment
evidence. Initial sandbox/import-path failures were resolved by using the repo
import path and permitted localhost access; the final suite passes without code
changes to runtime health checks or network protections.
