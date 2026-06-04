# Epic: UX v1

## Summary
Deliver the first complete user experience for core fantasy football workflows, from league setup through weekly play.

## In Scope
- League creation and configuration
- Team creation and management
- Draft flow (live or offline)
- Roster management (add/drop, lineup changes)
- Player search and detailed profiles
- Matchup view with scoring breakdown
- League standings and records

## Out of Scope
- Payments or premium tiers
- Multi-commissioner approvals
- Advanced analytics beyond core stats

## Success Criteria
- Users can create/join a league, draft a team, set a lineup, and view matchups and standings without guidance
- Core views are discoverable within two clicks from the league home
- Basic errors are handled with clear messages

## Workflow
1. User creates or joins a league.
2. User creates a team in the league.
3. Draft is completed (live or offline), populating team rosters.
4. User sets starters, adds/drops players, and manages lineup weekly.
5. User views matchups, scoring breakdowns, and standings.

## API Specs
- Leagues
  - `POST /leagues` create league
  - `GET /leagues` list leagues
  - `GET /leagues/:league_id` league detail
  - `PUT /leagues/:league_id` update league settings
- Teams
  - `GET /leagues/:league_id/teams` list teams
  - `POST /leagues/:league_id/teams` create team
- Draft
  - `GET /leagues/:league_id/draft` draft state
  - `POST /leagues/:league_id/draft/pick` submit pick
  - `POST /leagues/:league_id/draft/offline` submit offline picks
- Players
  - `GET /players` search/filter players
  - `POST /players` add players (admin/seed)
- Rosters
  - `GET /teams/:team_id/roster` roster detail
  - `POST /teams/:team_id/roster` add player
  - `DELETE /teams/:team_id/roster/:roster_entry_id` remove player
- Matchups
  - `GET /leagues/:league_id/matchups` weekly matchups
  - `GET /matchups/:matchup_id` matchup detail and scoring
- Standings
  - `GET /leagues/:league_id/standings` standings table

## UI Specs
- Leagues list + create form
- League detail with tabs: standings, schedule/matchups, teams, transactions
- Team detail + roster management
- Draft room with board, pick queue, and roster preview
- Player search and profile view
- Matchup detail with scoring breakdown

## Database Specs
- `leagues` core league metadata and settings
- `teams` teams linked to leagues
- `players` player directory
- `roster_entries` team rosters
- `drafts`, `draft_picks` draft state and picks
- `matchups` weekly head-to-heads
- `matchup_scores` player scoring per matchup
- `standings` computed or cached standings by week
