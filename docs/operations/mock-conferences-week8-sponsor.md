# Mock conference pools and Week 8 sponsorship

Mock Draft Setup reuses the conference choices from Create League: SEC, Big Ten,
Big 12, ACC, and Independent (Notre Dame). Any nonempty mix is allowed. The
selection travels in the new-mock URL, persists in local mock settings, and is
retained on reload, reset and canonical-player reconciliation. Old mocks without
conference settings retain the full approved pool. Small pools use the existing
pool-exhausted state; bots never add excluded players to fill a roster.

The existing public `/players?draft_eligible=true` contract accepts a comma-separated
`conference_codes` selection only without `league_id`. It reuses league pool
normalization and SQL filtering, ranks the selected full pool before pagination,
search and position filtering, and returns `draft_conference_codes`. Empty or
unsupported values and real-league overrides return 422. The React hook checks
that the server acknowledged a restricted selection before exposing the board;
an old server cannot silently return a full-pool board. Real drafts continue to
use their persisted league settings.

`api/app/services/weekly_challenge_sponsors.py` is the reusable sponsorship
configuration, keyed by `(season, week)`. Only `(2026, 8)` contains Pigskin Dispatch.
Round and individual-challenge reads return the same optional sponsor metadata.
The shared React strip appears above the Home challenge card, above the weekly
challenge grid, and on each individual challenge. Historical rounds resolve
their own sponsor; Weeks 1–7, Week 9 onward and later seasons remain unsponsored.
No challenge entry, deadline, score, award, or leaderboard state is changed.

The original `PigskinDispatchLogo.png` attachment supplied by Darin on October 17
is shipped byte-for-byte in `web/public/assets/sponsors/`. The square image uses
`object-contain`, without cropping, stretching or a replacement graphic. The
YouTube anchor uses the exact supplied channel URL, opens separately, and keeps
the challenge screen intact. Capacitor's existing navigation delegate forwards
external and new-window links to the operating system.

Rollout order: deploy the additive API contract, then publish/package the React
bundle, which includes the logo. Later round changes use server week resolution
and require no new app build. Previous native builds ignore the additive fields.

Verification includes backend conference validation, alias normalization, stable
pagination/ranks, default-pool compatibility and every individual challenge's
sponsor across Weeks 1–9 and the next season. Frontend tests cover saved mocks,
last-conference selection, all three sponsor surfaces, logo sizing and the exact
link. Phone/desktop browser flows cover selection, reload/reset, stale-server
refusal, Home/list/detail sponsorship, Week 7/9 absence, and the external channel
link. Related draft reliability and challenge pick-limit workflows are retained.
