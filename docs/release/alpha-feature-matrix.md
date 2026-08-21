# Alpha Feature Matrix

This inventory is based on the React route registry, FastAPI routers, worker
entry points, deployment manifest, and automated tests. Status describes the
current release-candidate evidence rather than a production deployment claim.

| Feature | Backend | React / mobile shell | Automated evidence | Certification status |
| --- | --- | --- | --- | --- |
| Public access and legal pages | Auth + public policy endpoints | Landing, signup, login, reset, privacy, terms, disclosure routes | Browser public-route E2E; frontend build | Verified locally; fresh RC CI pending |
| Authentication and account security | Session, refresh, password, lockout routers | Protected route shell and account views | Backend auth tests; real-stack auth suite | Automated coverage present; full multi-user release path pending |
| League creation, invites and joining | League, membership and invite services | Create/join flows | Backend league tests and browser workflows | Automated coverage present; five-user concurrency pending |
| Drafts and roster integrity | Draft room, picks, player locks, roster services | Mock and real draft rooms, roster views | Backend draft/lock tests; real-stack draft E2E | Automated coverage present |
| Players, profiles and availability | Player, projection, injury and provider routers | Player card, Summary → News → Stats, availability indicators | Backend/player and frontend tests | Automated coverage present; real report observation pending |
| Matchups and live scoring | Matchup/projection services, ESPN scoring worker | Live totals, timer, red-zone/possession state, projections | ESPN fixtures, projection, recalc and outlook tests | Full disposable worker replay pending |
| Waivers and trades | Waiver, ownership and trade services | Scoped waiver/trade flows | Backend workflow tests; browser trade E2E | Automated coverage present; full golden path pending |
| Playoffs and career profiles | Playoff, standings, career history services | Bracket and career screens | Backend schedule/postseason tests | Included in RC; migration rehearsal pending |
| Rival Week and opening week | Rivalry models and lifecycle logic | Rival/Oppening Week patches | Unit/component coverage | Automated coverage present |
| Notifications and injury alerts | Notification worker and injury processing | Settings league selection and alerts views | Backend notification/injury tests | Worker lifecycle verification pending |
| Chats and Saturday Pick 6 | Chat and Pick 6 routers | Chat and Pick 6 routes | API/browser tests | Automated coverage present |
| Settings and manager avatars | User profile/settings APIs | Photo picker, initials fallback, diagnostics/legal links | Frontend + auth/profile tests | Native TestFlight verification pending |
| Navigation, responsiveness and error states | N/A | React navigation registry and mobile shell | Typecheck, build, 25 browser E2E tests | Automated coverage present |
| Deployment and runtime health | Health/readiness endpoints, workers, config | Runtime compatibility shell | Manifest/config/health tests and read-only production health | Release contract fixed; fresh RC CI pending |

Deliberate scoped redirects such as `/waivers`, `/watchlists`, and `/stats`
resolve to the corresponding active-league screen. `/coming-soon` is a
deliberate placeholder and must not advertise unfinished alpha functionality.

No row may be considered production-certified until the release candidate has
its own successful CI checks and the remaining P0/P1 ledger entries are closed.
