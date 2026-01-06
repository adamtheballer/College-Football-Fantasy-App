# Feature: Team Creation and Management

## Description
Let users create a team within a league, customize identity, and manage team metadata.

## User Stories
- As a user, I can create or rename my team.
- As a user, I can set a team logo or avatar.
- As a commissioner, I can view all teams in the league.

## Acceptance Criteria
- Team creation includes name and owner identity.
- Team name and logo can be edited before the season starts.
- League home lists all teams with current owners.

## Workflow
1. User selects a league from the leagues list.
2. User opens the "Create team" form and enters team name and optional owner name.
3. System validates uniqueness of the team name within the league.
4. Team is created and shown in the league team list.
5. User edits team name or logo/avatar from the team settings view.

## API Specs
- `GET /leagues/:league_id/teams`
  - Response: list of teams for a league
- `POST /leagues/:league_id/teams`
  - Request body: `name`, `owner_name`, optional `logo_url`
  - Response: created team
- `GET /teams/:team_id`
  - Response: team detail (name, owner, league)
- `PUT /teams/:team_id`
  - Request body: `name`, `owner_name`, optional `logo_url`
  - Response: updated team
- `DELETE /teams/:team_id`
  - Response: 204 on success (commissioner-only)

## UI Specs
- Team creation form
  - Fields: team name (required), owner name (optional), logo/avatar (optional)
  - Validation: inline error on duplicate team name
  - Primary action: Create team
- Team list
  - Table or cards with team name, owner, and league
  - Action: select team for management
- Team settings
  - Editable name and owner
  - Logo/avatar upload or URL input
  - Save/cancel actions

## Database Specs
- Table: `teams`
  - Columns: `id`, `league_id`, `name`, `owner_name`, `logo_url`, `created_at`, `updated_at`
  - Unique constraint: `league_id` + `name`
