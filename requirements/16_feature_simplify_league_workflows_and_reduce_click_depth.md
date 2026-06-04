# Feature: Simplify League Workflows and Reduce Click Depth

## Summary

Rework the React app’s navigation and league-specific workflows so users can get to their real task in one or two decisions instead of navigating through multiple intermediate pages. The primary focus is simplifying league entry, making roster management feel immediate, and reducing repeated league selection across the app.

This story is a UX architecture and interaction story. It is not a visual polish effort. The goal is to reduce friction in the supported product surface and make the app feel league-centric and task-first.

## Problem

The current React app is organized around global page buckets like `Leagues`, `Roster`, `Stats`, and `Settings`, but the user’s real jobs are league-specific:

- get back into my league
- set my lineup
- manage my roster
- enter the draft
- add or drop a player
- act on an alert
- research players for my current league

That mismatch creates unnecessary click depth and context switching:

- users often choose a page first, then choose a league, then choose an action
- the same league context has to be reselected across multiple pages
- the league hub is still more informational than operational
- roster setup and roster management are several clicks in
- the draft lobby adds an extra step before the user reaches the live draft room
- alerts and stats are not strongly connected to the league or player action the user wants to take next

The result is that the app feels busy and indirect even when the backend contract exists.

## User Goals

- As a returning user, I can resume work in my active league without navigating through multiple hubs.
- As a league member, I can open my team and roster directly.
- As a commissioner, I can invite managers and manage the league from one clear command center.
- As a drafting user, I can enter the live draft room immediately when it is actionable.
- As a user researching players, I can move from roster, waivers, watchlists, alerts, and stats without losing league context.
- As a user updating one setting or handling one alert, I can complete that job and leave quickly.

## In Scope

- Add persistent active-league context to the React shell
- Reorganize league navigation around user jobs instead of generic page buckets
- Turn the league hub into the primary action surface for league-specific tasks
- Make roster flows owned-team-first and league-aware by default
- Remove unnecessary intermediate steps such as mandatory draft-lobby entry
- Make alerts actionable and stats entry points clearer
- Reduce mode switching and repeated decisions in watchlists and related research flows
- Improve route-to-task continuity after login, signup, create league, and join league

## Out of Scope

- Full visual redesign of the application
- Backend permission model changes beyond what is needed to support the UX flows
- New fantasy features such as trades, advanced matchup analysis, or commissioner tooling not already planned
- Replacing the existing design language wholesale

## User Stories

- As a signed-in user, when I open the app I can immediately resume my current league instead of starting from the top-level navigation.
- As a signed-in user, when I open roster-related pages I land in my active league and on my owned team by default.
- As a signed-in user, when a draft is available I can enter it directly from the league card or league hub.
- As a signed-in user, I can switch leagues once and have that context persist across roster, waiver, watchlist, and research pages.
- As a signed-in user, alerts take me directly to the league, player, or roster action I need to handle.
- As a commissioner, the league hub surfaces invite, draft, and settings actions without burying them below overview content.

## UX Principles

- Task-first over page-first
- League context should persist until the user explicitly changes it
- The first screen in a flow should present the next likely action, not only metadata
- Intermediate pages should exist only if they add meaningful decision value
- Default to the user’s owned team when the user intent is personal roster management
- Loading, empty, and error states should preserve context and offer the next useful action

## Detailed UX Requirements

### 1. Add Persistent Active-League Context

- The app shell in `web/client/components/Layout.tsx` must support an `active league` state for signed-in users.
- When a user opens a league from the leagues list, creates a league, joins a league, or enters a league hub, that league becomes the active league.
- Pages that are inherently league-scoped should use the active league by default:
  - `/rosters`
  - `/waivers`
  - `/watchlists`
  - `/league/:leagueId/draft`
  - `/league/:leagueId/lobby` if still retained
- If the user has only one league, the app should auto-select it and avoid asking the user to choose again.
- If the user has multiple leagues, league switching should be available from a lightweight control in the shell or page header rather than forcing navigation back to `/leagues`.
- Active-league selection should persist across refresh and re-login where feasible.

### 2. Move From Page-First Navigation to Task-First Navigation

- The primary shell navigation should reflect user jobs more clearly than the current page bucket model.
- The navigation should be simplified conceptually toward:
  - `Home`
  - `My League`
  - `My Team`
  - `Research`
  - `Alerts`
  - `Account`
- If the current route structure is preserved in the short term, labels and entry points still need to behave like task shortcuts instead of generic destinations.
- The navigation should minimize cases where the user lands on a page that immediately asks them to choose a league before they can do anything.

### 3. Rework Home Into an Operational Dashboard

- The home page should prioritize “resume what matters now” over decorative overview content.
- Logged-in users should see one-click actions for:
  - resume last active league
  - open my roster
  - enter draft if relevant
  - review alerts
  - join a league by code
- Logged-out users should see direct task intent:
  - create league
  - join by invite code
  - sign in
- Home content that does not help the next action should be demoted below actionable items.

### 4. Rework Leagues Into a League Switcher and Action Launcher

- The leagues list should help users open the correct league fast, not only browse cards.
- League cards in `web/client/pages/Leagues.tsx` should support multiple direct actions:
  - `Open League`
  - `My Team` or `Roster`
  - `Enter Draft` when relevant
- The primary CTA on each card should adapt to league state:
  - if draft is imminent or live, emphasize `Enter Draft`
  - if the league is newly created, emphasize `Invite Managers`
  - if the user needs roster work, emphasize `My Team`
- The entire league card should be clickable for the default action.
- The most recently active league should be visually prioritized.
- The create and join actions should remain available, but they should not feel detached from the rest of the flow.

### 5. Turn the League Hub Into the Primary Command Center

- `web/client/pages/LeagueDetail.tsx` should be action-first.
- The top area of the league hub should present the next likely actions before descriptive overview panels.
- Core actions surfaced at the top should include:
  - `My Team`
  - `Waiver Wire`
  - `Enter Draft` or `Draft Lobby`
  - `Invite Managers`
  - `League Settings` for commissioners
- The first CTA should be role-aware and state-aware:
  - commissioner in an unfilled league: `Invite Managers`
  - member near draft time: `Enter Draft`
  - member outside draft: `My Team`
- Informational overview content should remain available, but below primary actions.
- The workspace contract should power this page so actions and states are grounded in the user’s actual league context.

### 6. Make Roster Flow Owned-Team-First

- `web/client/pages/Rosters.tsx` should default to the user’s owned team in the active league.
- The first thing the user sees should be “my team” rather than a multi-card league picker.
- League-wide roster browsing should become a secondary view or tab:
  - `My Team`
  - `League Rosters`
- If the user has no roster entries, the page should still feel like their team page and guide them toward the next useful action:
  - `Go to Draft`
  - `Open Waiver Wire`
  - `Join Draft When Ready`
- The flow to get from active league to roster should be one click or less once the user is signed in.

### 7. Reduce Clicks in Waiver and Watchlist Flows

- `web/client/pages/WaiverWire.tsx` should inherit active league automatically.
- The user’s owned team should be preselected without extra input.
- The add/drop flow should reduce repetitive decisions where possible:
  - preselect a likely drop candidate
  - suggest the target slot
  - make league/team context implicit
- `web/client/pages/Watchlist.tsx` should avoid forcing a browse-vs-watchlists mode decision up front.
- The default saved state should be a built-in personal watchlist, such as `My Watchlist`.
- Creating multiple named watchlists should be optional, not required before the first save.
- Players saved from browse should require the fewest possible actions.

### 8. Remove Unnecessary Draft-Lobby Step

- If the live draft room is actionable, users should be able to enter it directly from:
  - home
  - league card
  - league hub
- `web/client/pages/DraftLobby.tsx` should only act as an informational staging page when the room is not yet actionable.
- The draft lobby should not be a mandatory checkpoint if the user’s true goal is to draft.
- Draft entry labels should reflect the real action:
  - `Enter Draft`
  - `Resume Draft`
  - `Draft Countdown`

### 9. Make Alerts Actionable

- `web/client/pages/Alerts.tsx` should not be a dead-end feed.
- Every alert row should offer a clear next action aligned to the alert type:
  - `View Player`
  - `Open League`
  - `Open My Team`
  - `Adjust Lineup`
  - `Review Waiver`
- Alerts should preserve league and player context so the user does not have to search again after clicking.

### 10. Clarify Stats and Research Entry Points

- `web/client/pages/Stats.tsx` is currently overloaded.
- The research experience should be broken into clearer entry points such as:
  - team research
  - player compare
  - player outlook
  - user leaderboard
- If full route splitting is deferred, the page still needs a much clearer first decision and persistent filter memory.
- Research should be reachable directly from:
  - waiver wire player rows
  - watchlist player rows
  - alerts
  - roster entries

### 11. Simplify Settings for Single-Task Visits

- `web/client/pages/Settings.tsx` should support “change one thing and leave.”
- Settings should be broken into smaller sections or tabs such as:
  - notifications
  - account
  - league preferences
- Simple toggles should autosave when appropriate or use section-level save instead of one long-form global save action.
- The page should reduce scanning and scrolling cost even if click count is already low.

### 12. Preserve User Intent Across Auth and Entry Flows

- Login and signup should preserve the user’s task intent:
  - create a league
  - join by code
  - return to a protected page
- After signup, the user should not be dropped into a generic path if the originating intent is known.
- Non-functional social auth affordances should be removed or clearly disabled so they do not compete with the real path.

## Information Architecture Direction

Recommended target model:

- Home: resume and high-priority actions
- My League: active league command center
- My Team: roster, lineup, transactions, waiver entry
- Research: waivers, player search, watchlists, stats
- Alerts: actionable notifications
- Account: settings and preferences

Short-term compatibility is acceptable, but the behavior should move toward this model even before the labels fully change.

## Technical Notes

- Use React app shell state or persisted query-backed state for active-league context
- Deep-linking should continue to work for direct league routes
- The active league model should not break users with multiple leagues
- The league workspace contract should be treated as the source of truth for role-aware league actions
- Existing routes can be preserved initially while changing the behavior and defaults
- This story should be coordinated with:
  - [10_feature_frontend_architecture_consolidation.md](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/requirements/10_feature_frontend_architecture_consolidation.md)
  - [12_epic_react_frontend_delivery.md](/Users/development/Desktop/Sandbox/code/College-Football-Fantasy-App/requirements/12_epic_react_frontend_delivery.md)

## Success Metrics

- Reduce the number of clicks from app entry to `my roster` for a signed-in user
- Reduce the number of clicks from league selection to draft room entry
- Reduce the number of repeated league selections across a session
- Increase successful completion of create/join/resume flows
- Reduce abandonment on the leagues page and roster page

## Acceptance Criteria

- Signed-in users can open roster-related pages and land in their active league without manually reselecting it.
- The league hub surfaces direct task actions before descriptive overview content.
- A user can reach their team roster from the main navigation in one step after sign-in.
- A user can reach the live draft room directly when it is actionable, without a mandatory intermediate lobby.
- League cards expose more than one meaningful action and reflect the current league state.
- The home page provides a clear resume path for returning users.
- Alerts include deep links or action CTAs that take the user to the relevant player, team, or league context.
- Stats and research entry points are clearer and do not force the user through an overloaded multi-mode page before they can start.
- Watchlist and waiver flows inherit active league context and reduce unnecessary setup decisions.
- Non-functional auth affordances that increase decision noise are removed or clearly disabled.

## Non-Goals

- Redesigning the visual style from scratch
- Building new fantasy features outside current supported workflows
- Replacing the backend auth model as part of this story
- Shipping every IA change in one release if an incremental rollout is safer

## Risks

- Changing navigation too aggressively could confuse existing users if migration is abrupt
- Active-league persistence must not create hidden state that makes users unsure which league they are operating in
- League-scoped defaults must still support users who intentionally switch between multiple leagues often
- Deep-link compatibility must be preserved during IA changes

## Rollout Plan

### Phase 1: Low-Risk Click Reduction

- Add active-league persistence
- Make league cards multi-action
- Make home operational for signed-in users
- Add direct draft entry where the room is actionable
- Remove non-functional auth distractions

### Phase 2: League-Centric Task Flow

- Rework league hub into the primary command center
- Rework roster into `My Team` first, league rosters second
- Inherit active league in waiver and watchlist flows
- Add actionable alert links

### Phase 3: Research and Account Cleanup

- Clarify stats/research entry points and route model
- Simplify settings into smaller task-based sections
- Clean up remaining page-first flows that force extra choices before action

## Testing and Validation

- Add UX-oriented browser coverage for:
  - resume last active league
  - open my roster from active league
  - direct draft entry when available
  - create league fast path
  - join by invite code with preserved intent
  - actionable alert navigation
- Track click depth for core flows before and after implementation
- Validate multi-league behavior so active-league persistence does not cause cross-league confusion
