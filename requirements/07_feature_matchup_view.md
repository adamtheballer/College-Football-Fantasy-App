# Feature: Matchup View with Scoring Breakdown

## Description
Show head-to-head matchups with live or final scoring by player and position.

## User Stories
- As a user, I can view my current matchup score.
- As a user, I can see scoring by player and position.
- As a user, I can compare projected vs actual points.

## Acceptance Criteria
- Matchup view displays both teams, starters, and bench totals.
- Opponent points and projections are visible alongside the user's team at all times.
- Player rows show points and scoring categories.
- Matchup view updates as scoring changes.

## Workflow
1. User selects a league and navigates to Matchups.
2. User selects the current week or a past week.
3. System loads head-to-head matchups for the week.
4. User opens a matchup to view per-player scoring.
5. Scores update as results are processed.

## API Specs
- `GET /leagues/:league_id/matchups`
  - Query params: `week`
  - Response: list of matchups with team summaries
- `GET /matchups/:matchup_id`
  - Response: matchup details with player scoring
- `GET /matchups/:matchup_id/scoring`
  - Response: per-player scoring breakdown and totals

## UI Specs
- Matchups list
  - Week selector and matchup cards
  - Team names, projected/actual totals
- Matchup detail
  - Side-by-side team panels with both scores visible
  - Header with current score, projected score, and win probability
  - Player rows with points and scoring categories
  - Totals for starters and bench

## Database Specs
- Table: `matchups`
  - Columns: `id`, `league_id`, `week`, `home_team_id`, `away_team_id`, `status`
- Table: `matchup_scores`
  - Columns: `id`, `matchup_id`, `team_id`, `player_id`, `points`, `projected_points`, `scoring_json`
