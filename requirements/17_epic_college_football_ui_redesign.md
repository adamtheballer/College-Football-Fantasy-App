# Epic: College Football UI Redesign

## Summary

Redesign the React frontend into a polished, colorful, modern college-football fantasy product. The redesign should replace the current heavy neon/video-game treatment with a simpler, more readable college-football aesthetic while preserving routes, API integrations, permissions, scoring states, draft behavior, and league workflows.

This epic is a design-system and product-surface redesign. It should be delivered in small reviewable phases, not as one large unreviewable visual rewrite.

## Problem

The current app has a strong dark fantasy-sports direction, but the styling is too scattered and visually heavy for a public fantasy product:

- global theme tokens exist, but many pages still hardcode colors, gradients, radii, glows, and card structures
- the shell and page layouts lean toward a navy sci-fi/video-game look instead of a clean college sports product
- repeated custom panels and nested cards make dense fantasy data harder to scan
- route-specific UI patterns are duplicated instead of expressed through shared product components
- mobile navigation and dense tables need more intentional treatments
- live, projected, final, corrected, delayed, locked, and unavailable states need clearer semantic visual treatment

## Current Frontend Audit

| Area | Current implementation | Main problem | Recommended redesign |
|------|------------------------|--------------|----------------------|
| Frontend stack | React 18, Vite, TypeScript, Tailwind, Radix/shadcn-style primitives, TanStack Query, Vitest, Playwright | Stack is usable and should not be replaced | Build on the existing stack with semantic product components |
| Routing | Route definitions live in `web/client/App.tsx` with lazy-loaded pages and `ProtectedRoute` | Routes are broad but stable | Preserve routes; redesign presentation only |
| App shell | `web/client/components/Layout.tsx` owns sidebar, top bar, guide state, floating actions, draft-room shell exceptions | Shell mixes navigation, brand styling, auth display, and visual effects in one component | Split into `AppShell`, `DesktopSidebar`, `MobileNavigation`, and `TopBar` |
| Theme | HSL CSS variables in `web/client/global.css`; Tailwind maps core tokens in `web/tailwind.config.ts` | Existing tokens are too generic and many semantic states are missing | Add semantic college-fantasy tokens for surface, brand, states, scoring, lock, and alerts |
| Decorative background | `BackgroundEffects` plus global gradients and heavy panel shadows | Effects are overused and can compete with dense data | Use calmer shared background layers, yard-line/play-diagram marks, and restrained paint accents |
| UI primitives | `web/client/components/ui/*` provides generic buttons/cards/dialogs/tables/tabs/sidebar | App-specific fantasy variants are spread across pages | Add product primitives such as `SurfaceCard`, `StatCard`, `StatusBadge`, `PlayerRow`, `EmptyState`, `ErrorState` |
| Tables | Pages style table rows independently | Dense fantasy data lacks consistent responsive behavior | Standardize `DataTable` and mobile card/table alternatives |
| Player cards/modals | Player detail UI is custom and palette-heavy | Modal behavior and metadata density need stronger consistency | Centered modal with backdrop blur, close-on-overlay, accessible focus handling, and richer player metadata only from real data |
| Auth pages | Existing login/signup/verification pages use current app styling | Public onboarding needs simpler, more trustworthy forms | Redesign around readable forms, clear validation, verification/resend states |
| Tests | Vitest and Playwright exist; E2E uses local Vite preview | Visual redesign has limited snapshot/DOM coverage today | Add focused route render tests and E2E smoke for shell, navigation, key pages, and modal behavior |

## Visual Direction

Use the supplied reference images as direction, not as assets or pixel templates:

- deep stadium-navy canvas with near-black application surfaces
- vivid college-sports royal blue as the dominant primary action color
- controlled pink, gold, cyan, and green accents for emphasis and state
- bold athletic display typography for page titles and large score values
- readable interface typography for tables, controls, forms, and metadata
- subtle field markings, play-diagram marks, paint strokes, and scoreboard dividers
- strong fantasy-sports hierarchy for scores, projections, player names, matchup state, roster locks, and deadlines
- calmer data surfaces than the marketing-style reference artwork

Do not use copyrighted player photos, school logos, conference marks, jersey designs, or reference-image artwork unless those assets are already licensed and present in the repository.

## Design Principles

- Real data first; decoration must never hide fantasy state or actions.
- One design system; no page-specific visual language forks.
- Color communicates hierarchy and state; do not make every card a different color.
- Dense data pages should be calmer than marketing and dashboard pages.
- Mobile layouts should be intentionally designed, not squeezed desktop layouts.
- No fake controls, dead buttons, or mock-only states on production routes.
- Accessibility and contrast are non-negotiable.

## In Scope

- Design tokens and Tailwind theme extensions
- Shared app shell and responsive navigation
- Shared product components for cards, scores, badges, tables, states, filters, and dialogs
- Home dashboard redesign
- Matchup page redesign
- Player discovery and watchlist redesign
- Roster page redesign
- Draft home, lobby, and room redesign
- League hub, settings, waivers, and trade UI redesign
- Auth page redesign
- Admin and commissioner UI cleanup
- Responsive, accessibility, and visual consistency pass
- Frontend tests and browser verification for redesigned routes

## Out of Scope

- Backend feature work unrelated to presentation
- Replacing React, Vite, Tailwind, Radix, TanStack Query, or the API client stack
- Changing route semantics without a separate routing/product decision
- Introducing copyrighted sports assets or unlicensed player imagery
- Replacing real API integrations with mock data
- Completing waivers or trades if the backend workflow is not implemented in that branch

## Foundation Files

The redesign should start with these files:

- `web/client/global.css`
- `web/tailwind.config.ts`
- `web/client/components/Layout.tsx`
- `web/client/components/BackgroundEffects.tsx`
- `web/client/components/FloatingQuickActions.tsx`
- `web/client/components/ui/button.tsx`
- `web/client/components/ui/card.tsx`
- `web/client/components/ui/badge.tsx`
- `web/client/components/ui/dialog.tsx`
- `web/client/components/ui/table.tsx`
- `web/client/components/ui/tabs.tsx`

Recommended new shared component area:

- `web/client/components/app-shell/`
- `web/client/components/fantasy/`
- `web/client/components/states/`

## Design Tokens

Add or standardize semantic tokens for:

- `background-canvas`
- `background-sidebar`
- `background-surface`
- `background-surface-raised`
- `background-surface-hover`
- `border-subtle`
- `border-strong`
- `text-primary`
- `text-secondary`
- `text-muted`
- `brand-primary`
- `brand-primary-hover`
- `accent-pink`
- `accent-gold`
- `accent-cyan`
- `success`
- `warning`
- `danger`
- `live`
- `projected`
- `final`
- `corrected`
- `delayed`
- `unavailable`
- `locked`

State colors must pass WCAG AA for text or include non-color indicators such as labels, icons, and copy.

## Shared Components

Build or refactor these reusable product components before broad page work:

- `AppShell`
- `DesktopSidebar`
- `MobileNavigation`
- `TopBar`
- `PageHeader`
- `SurfaceCard`
- `StatCard`
- `ScoreCard`
- `MatchupCard`
- `PlayerRow`
- `PlayerTable`
- `PositionBadge`
- `TeamAvatar`
- `StatusBadge`
- `LiveIndicator`
- `ProjectionIndicator`
- `LockIndicator`
- `EmptyState`
- `ErrorState`
- `SkeletonState`
- `ConfirmationDialog`
- `FilterBar`
- `SearchInput`
- `SegmentedControl`
- `MobilePlayerCard`

## Implementation Phases

### Phase 1: Tokens, Theme, and Primitives

- Extend CSS variables and Tailwind theme with semantic tokens.
- Reduce scattered hardcoded colors in shared primitives.
- Add product-level wrappers for surfaces, stats, badges, and states.
- Add reduced-motion-safe transitions and visible focus styles.
- Add Storybook only if the repository already supports it; otherwise use route-based examples and component tests.

Acceptance criteria:

- core tokens are centralized
- new components use tokens rather than scattered hex values
- existing pages still render
- `npm --prefix web run typecheck` passes
- focused component tests pass

### Phase 2: App Shell and Navigation

- Split `Layout.tsx` into app-shell components.
- Add responsive desktop sidebar, top bar, and mobile bottom navigation.
- Preserve draft-room shell exceptions and auth flow exceptions.
- Add active-route treatment using the new brand system.
- Keep commissioner/admin navigation separated from normal manager navigation.

Acceptance criteria:

- desktop, tablet, and mobile navigation work
- no route loses access
- auth, draft room, create league, and admin routes still render
- no horizontal page scrolling at mobile widths

### Phase 3: Home and Matchup

- Redesign the logged-in home dashboard around current league, matchup, roster completeness, deadlines, standings, and recent activity.
- Make matchup the flagship scoring page with large score hierarchy, scoring state, freshness, lineups, locks, and warnings.
- Do not imply live scoring when data is projected, stale, delayed, unavailable, final, or corrected.

Acceptance criteria:

- home dashboard is action-first
- matchup state labels are honest and visually distinct
- loading, empty, error, and unavailable states exist
- responsive layouts work at 360px, 768px, 1024px, and desktop widths

### Phase 4: Players, Watchlist, and Roster

- Standardize player discovery tables and mobile cards.
- Add filters and availability state treatments without changing backend behavior.
- Redesign roster for starters, bench, projections, game state, locks, and validation.
- Preserve pre-draft empty roster behavior: placeholder slots show `N/A` and projections show `-`.

Acceptance criteria:

- player tables are readable and responsive
- no add/claim action appears when backend does not allow it
- roster locks and empty states are clear
- real player card opens only for real player IDs

### Phase 5: Draft Room

- Redesign draft home, lobby, and live draft room around clock, current pick, upcoming picks, available players, queue, roster needs, and connection state.
- Keep real-time behavior and draft API calls intact.
- Ensure large player boards remain readable.

Acceptance criteria:

- mock draft and real draft player pools load through existing hooks
- draft actions remain tied to backend state
- unavailable players and locked picks are visually clear
- reconnect/error state is visible

### Phase 6: League, Waivers, Trades, Auth, Admin

- Redesign league command center, settings, standings, schedules, manager rosters, trade history, and draft results.
- Redesign waivers and trades to reflect actual backend capability.
- Redesign login, signup, verify email, forgot password, and reset password flows.
- Redesign admin/commissioner pages for repair-oriented workflows without hiding operational data.

Acceptance criteria:

- no preview-only workflow is presented as fully functional
- auth forms have clear validation and accessible labels
- admin actions have confirmation and error states
- non-admin paths remain blocked where appropriate

### Phase 7: Responsive, Accessibility, and Regression Pass

- Verify 360px, 390px, 768px, 1024px, 1280px, and 1440px layouts.
- Verify keyboard navigation and focus states.
- Verify contrast for tokens and state badges.
- Verify dialogs fit the viewport and close predictably.
- Run frontend typecheck, tests, build, and E2E where environment permits.

Acceptance criteria:

- no clipped controls
- no unintended horizontal page scroll
- no console errors in core flows
- frontend verification commands pass or have documented environmental blockers

## Page-Level Requirements

### Home Dashboard

- personalized welcome
- current league/team selector where data exists
- current-week matchup summary
- projected/live/final/corrected/delayed/unavailable state
- roster completeness and locked-player alerts
- compact standings and recent activity
- direct actions such as `Manage Roster`, `View Matchup`, `Enter Draft`, and `Join League`

### Matchup

- large team score/projection values
- team names and records
- score state and freshness
- side-by-side starters on desktop
- stacked or tabbed team views on mobile
- fantasy points per player
- kickoff and lock indicators
- provider delay/unavailable warnings

### Players and Watchlist

- search and position filters
- league-aware availability
- projection/points sorting where data exists
- watchlist toggle
- add/claim/unavailable state based on backend capability
- sticky desktop header and mobile card layout

### Roster

- starters and bench separation
- position slots
- projection/live/final values
- opponent and kickoff
- injury or availability status where data exists
- locked state and validation errors
- pre-draft placeholder slots with `N/A` names/schools/opponents and `-` projections

### Draft

- draft clock
- current pick and upcoming picks
- player search/filtering
- draft board
- roster needs
- queue/watchlist
- recent picks
- connection and reconnect state

### League

- standings
- schedule
- members
- league activity
- scoring, roster, and transaction settings
- commissioner controls only when authorized

### Waivers and Trades

- show real claim/trade lifecycle only when backend supports it
- use honest unavailable/beta states when workflow is incomplete
- include status timelines and cancellation/acceptance controls only when valid

### Auth

- login
- signup
- verify email
- forgot password
- reset password
- clear validation, accessible labels, verification/resend states

### Admin and Commissioner

- clear tables, filters, status badges, repair actions, audit history, confirmation dialogs, and detailed errors

## Accessibility Requirements

- WCAG AA contrast for normal text and controls
- semantic headings and landmarks
- real buttons and links
- visible focus styles
- associated labels for inputs
- accessible names for icon-only buttons
- no state communicated only by color
- reduced-motion support
- controlled live-score announcements

## Responsive Requirements

Test at:

- 360px
- 390px
- 768px
- 1024px
- 1280px
- 1440px

Each breakpoint must avoid clipped controls, accidental page-level horizontal scrolling, unusable tables, oversized dialogs, hidden primary actions, and unreadable score/player status.

## Testing Requirements

Run the actual repository commands after each meaningful phase:

- `npm --prefix web run typecheck`
- `npm --prefix web test`
- `npm --prefix web run build`
- `npm --prefix web run test:e2e`

Add or update tests for:

- shell navigation
- mobile navigation
- route rendering
- player modal open/close behavior
- loading, empty, error, and disabled states
- matchup score state rendering
- roster pre-draft placeholder rendering
- draft room player table rendering

## Definition of Done

- one coherent design system is used across major routes
- routes, data flows, permissions, and business logic are preserved
- fantasy data is easier to scan than before
- mobile layouts are intentional
- live-scoring state remains honest
- accessibility requirements are met
- frontend typecheck, tests, build, and E2E pass or have documented environmental blockers
- no unlicensed sports imagery is introduced
- no fake controls or dead interactions are introduced

## GitHub Tracking

Per project instructions, this requirements document should be mirrored into a GitHub epic/issue set before implementation begins. Suggested issue breakdown:

1. UI Redesign Phase 1: Tokens, Theme, and Primitives
2. UI Redesign Phase 2: App Shell and Navigation
3. UI Redesign Phase 3: Home and Matchup
4. UI Redesign Phase 4: Players, Watchlist, and Roster
5. UI Redesign Phase 5: Draft Room
6. UI Redesign Phase 6: League, Waivers, Trades, Auth, Admin
7. UI Redesign Phase 7: Responsive, Accessibility, and Regression Pass
