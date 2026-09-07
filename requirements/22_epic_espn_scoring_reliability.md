# Epic: ESPN Scoring Reliability Controls

## Summary

The ESPN scoring worker must continue scoring healthy games when one provider
event is incomplete, avoid unbounded polling and alert noise after final
games, and maintain verified player identity coverage before games begin.

## In Scope

1. Quarantine a repeatedly incomplete provider game with durable per-game
   backoff while all other due games continue to score.
2. Emit each active operational condition once per incident window instead of
   logging the same provider condition every worker iteration.
3. Stop high-frequency polling after a final result is stable; preserve a
   bounded, low-frequency reconciliation safety check.
4. Accept an unordered final correction only after the same scoring-state
   response is observed twice consecutively.
5. Run bounded pregame ESPN identity reconciliation for relevant unverified
   player records without blocking live scoring.

## Out of Scope

- Changing league scoring rules, matchup schedules, roster data, or accepted
  historical scores without a verified provider correction.
- Guessing player identities from fuzzy name matches.

## Acceptance Criteria

- A single game that returns incomplete data three times is delayed for a
  longer per-game retry interval and does not make the worker heartbeat fail.
- Successful games still update in the same worker cycle when another game is
  quarantined.
- A stable final game is not continuously rediscovered or polled every few
  minutes; its next reconciliation is delayed to the safety interval.
- A differing final payload without an ESPN revision remains unaccepted on
  first observation and is accepted only when the same scoring-state hash is
  observed again.
- Operational alerts are deduplicated by code and affected game/season/week
  for a bounded incident window, while their occurrence count remains visible.
- Pregame identity work uses only exact ESPN roster/profile matches, is rate
  bounded, and cannot block a scoring cycle.
- Targeted unit tests cover all five behaviors and the migration upgrades on a
  disposable database.

## Data and Failure Ownership

- `provider_game_polls` owns retry, final-stability, and pending-correction
  state.
- `scoring_alert_incidents` owns alert suppression and occurrence counts.
- Rejected provider snapshots remain audit-only and never replace accepted
  scoring state.
- The worker process is unhealthy only when the iteration itself fails; an
  isolated provider game failure is reported as degraded data.

## Rollout

1. Apply the additive migration before deploying worker code.
2. Deploy API and worker together.
3. Verify a healthy heartbeat, no tight-loop final polls, and bounded alert
   emission from the Railway logs.
