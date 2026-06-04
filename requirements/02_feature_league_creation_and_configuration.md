# Feature: League Creation and Configuration

## Description
Allow a user to create a new league with configurable rules and settings, or join an existing league via invite.

## User Stories
- As a user, I can create a league with a name, size, and season start week.
- As a commissioner, I can configure scoring rules and roster limits.
- As a user, I can join a league via an invite code or link.

## Acceptance Criteria
- League creation requires a name and league size.
- Scoring and roster settings have defaults and are editable before draft.
- A shareable invite is generated after creation.
- Users can view league settings from the league home.

## Workflow
1. User selects "Create League" from the leagues list or home.
2. User enters league name, size, and season start week; defaults are pre-filled.
3. User reviews and optionally edits roster limits and scoring rules.
4. User submits and becomes commissioner; league home opens with invite code/link.
5. Another user joins via invite; user is prompted to create a team name.

## API Specs
- `POST /api/leagues`
  - Request body: `name`, `size`, `season_start_week`, `scoring_rules`, `roster_limits`
  - Response: `league_id`, `invite_code`, `commissioner_user_id`
- `GET /api/leagues/:league_id`
  - Response: league details, settings, teams summary
- `PATCH /api/leagues/:league_id/settings`
  - Request body: `scoring_rules`, `roster_limits`, `season_start_week`
  - Response: updated settings
- `POST /api/leagues/:league_id/invites`
  - Response: `invite_code`, `invite_link`
- `POST /api/leagues/join`
  - Request body: `invite_code`, `team_name`
  - Response: `league_id`, `team_id`

## UI Specs
- Create League form
  - Fields: league name, league size, season start week
  - Advanced settings accordion for scoring rules and roster limits
  - Primary action: Create League
- League Home header
  - League name, commissioner badge, invite code/link copy
- Settings view
  - Sections for scoring rules and roster limits with inline editing
  - Save and cancel actions
- Join League modal
  - Invite code input and team name field

## Database Specs
- Table: `leagues`
  - Columns: `id`, `name`, `size`, `season_start_week`, `commissioner_user_id`, `invite_code`, `created_at`, `updated_at`
- Table: `league_settings`
  - Columns: `league_id`, `scoring_rules_json`, `roster_limits_json`, `updated_at`
- Table: `teams`
  - Columns: `id`, `league_id`, `name`, `owner_user_id`, `created_at`, `updated_at`
