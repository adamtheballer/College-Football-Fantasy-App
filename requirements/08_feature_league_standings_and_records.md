# Feature: League Standings and Records

## Description
Display league standings with win/loss records and tiebreakers.

## User Stories
- As a user, I can view league standings at any time.
- As a user, I can see wins, losses, and points for/against.
- As a commissioner, I can verify tiebreaker order.

## Acceptance Criteria
- Standings show rank, team name, record, and points for/against.
- Tiebreakers apply consistently and are visible in a help tooltip.
- Standings are accessible from the league home.

## Workflow
1. User selects a league and opens Standings.
2. System loads standings for the current week.
3. User can view historical standings by selecting a week.
4. Tiebreaker rules are visible from an info tooltip or modal.

## API Specs
- `GET /leagues/:league_id/standings`
  - Query params: `week`
  - Response: standings rows with record, points for/against, rank, tiebreakers
- `GET /leagues/:league_id/standings/rules`
  - Response: tiebreaker rules and ordering logic

## UI Specs
- Standings view
  - Table with rank, team, record, points for/against
  - Week selector
  - Tiebreaker info tooltip/modal

## Database Specs
- Table: `standings`
  - Columns: `id`, `league_id`, `team_id`, `week`, `wins`, `losses`, `ties`, `points_for`, `points_against`, `rank`
- Table: `tiebreaker_rules`
  - Columns: `id`, `league_id`, `rules_json`, `updated_at`
