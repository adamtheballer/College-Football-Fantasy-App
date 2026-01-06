# Feature: Player Search and Detailed Profiles

## Description
Provide searchable player listings with filters and a detailed profile view containing stats and context.

## User Stories
- As a user, I can search players by name and filter by position or team.
- As a user, I can open a player profile to view season stats.
- As a user, I can see injury status and availability.

## Acceptance Criteria
- Search supports partial name matches.
- Filters include position and team as minimum.
- Player profile shows key stats, availability, and schedule summary.

## Workflow
1. User opens Players page.
2. User applies filters (position, school/team) or enters a search term.
3. System returns matching players with summary stats.
4. User opens a player profile for detailed stats and availability.

## API Specs
- `GET /players`
  - Query params: `search`, `position`, `school`, `limit`, `offset`
  - Response: list of players with summary fields
- `GET /players/:player_id`
  - Response: player detail, availability, recent stats
- `POST /players`
  - Request body: player attributes (admin/seed)
  - Response: created players

## UI Specs
- Player search
  - Filters: position, school/team, name search
  - Results table or cards with name, position, school, availability
- Player profile
  - Header with player name, school, position, status badge
  - Key stats summary and recent games list
  - Add to roster action (if eligible)

## Database Specs
- Table: `players`
  - Columns: `id`, `name`, `position`, `school`, `external_id`, `created_at`, `updated_at`
- Table: `player_stats`
  - Columns: `id`, `player_id`, `season`, `week`, `stats_json`, `created_at`
- Table: `player_status`
  - Columns: `player_id`, `status`, `updated_at`
