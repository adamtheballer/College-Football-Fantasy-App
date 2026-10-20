# Epic: First participation and trustworthy player leaders

## Summary

Implement the six approved product improvements and begin with a Home section
directly beneath Weekly Challenges showing each position's verified top performer.
React `web/` remains the canonical UI; preserve existing league/challenge rules.

## Confirmed choices

- Default leaders to the latest completed fantasy week, not the upcoming Week 8
  slate. Offer season-to-date and explicit week selection.
- My leagues shows each rostered player's positional rank in that league's
  eligible conference pool, calculated with that league's scoring. It does not
  rank teams' combined positional groups.
- QB, RB, WR, TE and K each have a portrait/name/school/FPTS card. Portraits
  honor the existing server image switch and have accessible fallbacks.

## Stories and acceptance criteria

### 1. Verified positional leaders and research

- Home renders five leader cards immediately beneath Weekly Challenges.
- Rankings use actual verified stats for one selected fantasy game per school
  and week, preserving Week 0/Week 1 mapping; never substitute projections.
- The default week is the latest completed week with verified facts. A stale
  or incomplete feed is visible and cannot fabricate an alphabetical zero board.
- A shared scoring service handles global standard and league scoring, finite
  numbers, negative/zero scores, ties, missing data, games played and timestamps.
- A linked `/player-rankings` view shows a paginated FPTS-descending table with
  position, period, search and league selectors. Player rows open existing cards.
- My players filters only after ranks are calculated against the whole eligible
  league pool. Every current roster player remains visible; missing stats have
  null points/rank and Pending, not a fabricated zero.
- League reads require membership and use the immutable scoring snapshot when
  available. Users cannot inspect another manager's private league by ID.
- GET `/player-rankings` accepts season, period (week/season), optional week,
  position, league_id, mine, search, limit<=100 and offset. Returns data/total/
  limit/offset, selected period, available weeks, scoring label, coverage and
  last-updated timestamp. GET `/player-rankings/leaders` uses the same service.

### 2. First challenge participation

- Home highlights one currently Open, unsubmitted, simple challenge (Lock of
  the Week first) with server deadline and a direct entry link. Existing modes
  remain discoverable. Closed/draft challenges never receive an Enter CTA.
- The simple entry shows one concise instruction, remaining selections and a
  clear submitted confirmation. Validation/pick limits and scoring stay server
  authoritative; a failed request never looks submitted.

### 3. Player-data health and freshness

- An admin-only health report checks completed selected games missing verified
  player facts, unusable scoring inputs, and stale reviewed injury feeds.
- A repeatable read-only health command returns a nonzero exit on actionable
  gaps and supports operations scheduling. Do not invent stats, bulk mark
  players healthy, or change published scores to make checks pass.
- New ranking surfaces expose last verified update and Pending/Final state.
- Health output is bounded, summarizes coverage and distinguishes a bye from
  missing data. Add the health check to an existing ongoing worker cadence.

### 4. Shorter first session and review timing

- New users receive a concise skippable guide; the historical 1.03 briefing
  applies to existing accounts rather than stacking a ten-screen recap after
  every new signup. Preserve authenticated one-time receipts.
- A first automatic review request becomes eligible after a submitted challenge
  or finalized played matchup. Account-wide once-only safeguards remain.
- Record authorization and native invocation distinctly. Neither means Apple
  displayed its sheet or accepted a review. No repeated automatic prompts for
  previously consumed accounts; browser visits cannot claim native reviews.

### 5. Home next actions

- Home displays bounded actionable items with direct links: own injured
  starters, lineup lock, incoming pending trades, and available unfinished picks.
- Server current time and verified league/player state determine deadlines.
- Errors offer retry; empty state says no urgent actions. Never turn a failed
  query into a healthy/complete state, show another user's roster, or send extra
  notifications without the existing preferences/deduplication policy.

### 6. Shareable competition

- All existing challenge formats gain safe challenge invite/result sharing,
  preserving existing experience-mode sharing and pre-lock lineup privacy.
- Sponsor links can open the current sponsored challenge directly, and existing
  creator referral attribution continues to work.
- League-filtered challenge leaderboards provide friend-group competition via
  existing league membership; require membership, rank within the selected group
  and preserve global board behavior. Never create fake entrants.

### 7. Participation measurement

- Add bounded, authenticated, idempotent first-party events for app/session
  activity, guide dismissal, challenge view/entry start/submission/share and
  notification open. Native version/build are recorded when available.
- Derive authoritative submissions from persisted ChallengeEntry records,
  rather than trusting a client 'submitted' event.
- Reuse the existing analytics opt-out. Do not store message content, email,
  full URLs/query strings, push tokens or credentials in event properties.
- Admin metrics show a clearly defined signup cohort, league membership,
  challenge funnel and return activity. Test/admin accounts are excluded by
  default and can be included explicitly. Distinguish accounts from people.
- Retain raw usage events for 90 days and report the retention policy.

## Verification and rollout

Publish this epic and seven matching GitHub stories. Test verified/final stat
selection, missing and zero data, league scoring/conference parity, pagination,
authorization, once-only review eligibility, telemetry opt-out/deduplication,
and Home/share interactions. Run backend and React tests, type checks, build,
and real-browser checks at phone/desktop sizes. Deploy additive backend contracts
and migrations before releasing the updated native bundle. Do not submit a new
App Store build without a new explicit submission request.


## Tracking

- Epic: #405
- Story 1: #406 · positional leaders and league roster ranks
- Story 2: #407 · first challenge entry
- Story 3: #408 · player facts and source health
- Story 4: #409 · short guide and review eligibility
- Story 5: #410 · Home next actions
- Story 6: #411 · safe sharing and league groups
- Story 7: #412 · participation measurement

Implementation and operational semantics: `docs/operations/activation-player-leaders.md`.
