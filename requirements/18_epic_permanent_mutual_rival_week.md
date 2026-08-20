# Epic: Permanent Mutual Rivalries and Rival Week

## Summary

Managers may form one mutually accepted, permanent rivalry per league after the draft completes. Rivalries are social metadata only: they never change scoring, projections, scheduling, standings, playoffs, waivers, trades, or draft behavior. Teams still play one canonical matchup per week. Their first scheduled meeting remains a normal game for early bragging rights; only their final scheduled meeting in a season receives Rival Week context and presentation.

## In Scope

- Invitation lifecycle: `PENDING`, `ACCEPTED`, `DECLINED`, `CANCELED`, `EXPIRED`, and `INVALIDATED`.
- One current rivalry binding per fantasy team per league, enforced by the database.
- Atomic acceptance, invalidation of competing pending invitations, deterministic notifications, and lazy 72-hour expiry.
- Server-derived rivalry and cross-season series context on matchup and home-carousel contracts.
- React rivalry selection/review UI, original app-owned Rival Week decoration, one-time reduced-motion-safe confetti, and responsive coverage.
- Exceptional archival only when a rival becomes ineligible; accepted rivalries cannot be changed through normal manager APIs.

## Out of Scope

- Scoring, lineup, projection, schedule, standings, playoff, waiver, trade, draft-order, and tiebreaker changes.
- Migration of the unmerged PR #71 rivalry model.
- Casual commissioner editing or a manager-facing change/remove-rival action.

## User Stories

- As a drafted-league manager, I can invite an eligible human league mate after acknowledging that acceptance is permanent.
- As a recipient, I can review the permanent consequences before accepting, declining, or ignoring an invitation.
- As a rival, I see Rival Week only for the final scheduled meeting with my rival that season; earlier meetings remain normal matchups.
- As a league manager, I retain my accepted rival across future seasons of the same league.

## API

- `GET /leagues/{league_id}/rivalry` returns current rivalry, eligible candidates, outgoing invitation, incoming invitations, and derived series.
- `POST /leagues/{league_id}/rivalry/invites` accepts `{ "recipient_team_id": integer }`.
- `POST /leagues/{league_id}/rivalry/invites/{invite_id}/accept|decline|cancel` enforces the caller's role and state transition.
- `GET /leagues/{league_id}/matchup` returns only server-derived rivalry context; the browser must not infer rivals from names.

## Database

- `league_rivalry_invites` stores invitation lifecycle and expiration.
- `league_rivalries` preserves an accepted or exceptionally archived relationship and snapshots identity at acceptance.
- `league_rivalry_bindings` has unique `(league_id, team_id)` rows, creating two bindings on acceptance.
- Canonical team-pair ordering and a unique rivalry pair prevent duplicate accepted relationships.

## Acceptance Criteria

- A manager has at most one accepted rival per league, and acceptance is mutual and atomic.
- Any eligible human league mate can be invited; bots, ownerless teams, self, outsiders, and already-bound teams cannot be invited.
- Pending invitations expire after 72 hours and senders can cancel before acceptance.
- Acceptance invalidates competing pending invitations involving either accepted team.
- Rivalries persist across league seasons and derive their record from canonical finalized matchups only.
- Rival Week never changes scheduling, score, projection, standings, or lineup behavior.
- Rival Week presentation is original, accessible, responsive, reduced-motion-safe, and only appears for the final scheduled rivalry matchup of the season.

## Tracking

GitHub tracking must link to this source-of-truth file and split delivery into model/lifecycle, matchup/home presentation, and verification stories.
