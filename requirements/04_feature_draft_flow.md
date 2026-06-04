# Feature: Draft Flow (Live or Offline)

## Description
Provide a draft experience where teams select players in a set order, supporting both live and offline drafts.

## User Stories
- As a user, I can see the draft order and upcoming picks.
- As a user, I can make a pick when it is my turn.
- As a commissioner, I can pause, resume, or complete an offline draft.

## Acceptance Criteria
- Draft order is displayed and updates after each pick.
- Picks are validated against roster limits and position rules.
- Offline draft allows manual entry of picks in order.
- Completed draft populates team rosters.

## Workflow
1. Commissioner starts a draft for a league and selects live or offline mode.
2. System generates the draft order and round count based on league size and roster limits.
3. During live draft, the active team makes a pick within the timer window.
4. During offline draft, commissioner submits picks in order or uploads a list.
5. Draft completes and rosters are populated from the final pick list.

## API Specs
- `POST /leagues/:league_id/draft`
  - Request body: `mode` (live|offline), `rounds`, optional `timer_seconds`
  - Response: draft metadata and order
- `GET /leagues/:league_id/draft`
  - Response: current draft state, order, picks
- `POST /leagues/:league_id/draft/pick`
  - Request body: `team_id`, `player_id`, `round`, `pick_number`
  - Response: created pick and updated draft state
- `POST /leagues/:league_id/draft/offline`
  - Request body: list of `team_id`, `player_id` in pick order
  - Response: applied picks and updated draft state
- `POST /leagues/:league_id/draft/complete`
  - Response: draft marked complete and rosters created

## UI Specs
- Draft setup modal
  - Mode selector (live/offline), rounds, timer
  - Start draft action
- Draft room
  - Draft board with rounds/picks
  - Current pick indicator and timer (live)
  - Team roster preview
  - Player search/filter and pick action
- Offline draft entry
  - Manual pick list form or CSV upload
  - Validate order and roster limits before apply

## Database Specs
- Table: `drafts`
  - Columns: `id`, `league_id`, `mode`, `rounds`, `timer_seconds`, `status`, `created_at`, `updated_at`
- Table: `draft_picks`
  - Columns: `id`, `draft_id`, `team_id`, `player_id`, `round`, `pick_number`, `created_at`
  - Unique constraint: `draft_id` + `pick_number`
