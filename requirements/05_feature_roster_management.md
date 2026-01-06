# Feature: Roster Management (Add/Drop, Lineup Changes)

## Description
Allow users to manage their roster, set starters, and make add/drop moves within league rules.

## User Stories
- As a user, I can move players between starting lineup and bench.
- As a user, I can add a free agent to my roster.
- As a user, I can drop a player from my roster.

## Acceptance Criteria
- Lineup changes respect position and roster limits.
- Add/drop transactions are recorded with timestamps.
- Users receive clear messages when moves are invalid.

## Workflow
1. User selects a league and team roster.
2. User moves players between starter slots and bench.
3. User searches free agents and submits add/drop.
4. System validates roster limits and position eligibility.
5. Roster updates are reflected in the team view and transaction log.

## API Specs
- `GET /teams/:team_id/roster`
  - Response: roster entries with player details and slot/status
- `POST /teams/:team_id/roster`
  - Request body: `player_id`, `slot`, `status`
  - Response: created roster entry
- `PUT /teams/:team_id/roster/:roster_entry_id`
  - Request body: `slot`, `status`
  - Response: updated roster entry
- `DELETE /teams/:team_id/roster/:roster_entry_id`
  - Response: 204 on success
- `GET /teams/:team_id/transactions`
  - Response: list of add/drop and lineup changes

## UI Specs
- Roster view
  - Sections for starters and bench
  - Position pills and player rows with quick actions
- Lineup editor
  - Drag-and-drop or select slot assignment
  - Save/cancel actions with validation errors
- Add/Drop modal
  - Player search with filters
  - Confirm add/drop actions
- Transactions panel
  - Timestamped list of roster changes

## Database Specs
- Table: `roster_entries`
  - Columns: `id`, `team_id`, `player_id`, `slot`, `status`, `created_at`, `updated_at`
  - Unique constraint: `team_id` + `player_id`
- Table: `transactions`
  - Columns: `id`, `team_id`, `type`, `payload_json`, `created_at`
