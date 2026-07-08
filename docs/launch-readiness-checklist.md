# Final Launch Readiness Checklist

This checklist is the public-release gate. Do not mark an item complete unless the implementation is merged, tested, and has clear evidence in code, CI, docs, or admin tooling.

## Scoring

- [ ] Canonical scoring engine merged
- [ ] Scoring settings validation
- [ ] Golden fixtures for every supported position: QB, RB, WR, TE, K
- [ ] Stat correction audit trail
- [ ] Lineup lock tested

## League

- [ ] League lifecycle states
- [ ] Settings versioning
- [ ] Invite expiry/revoke
- [ ] Commissioner tools audited

## Roster

- [ ] Add/drop transactional
- [ ] No duplicate ownership
- [ ] Lineup legality enforced server-side
- [ ] IR/bench/taxi behavior tested

## Draft

- [ ] Server draft clock
- [ ] Autopick
- [ ] Pause/resume/undo
- [ ] Race-condition tests
- [ ] Draft completion creates legal rosters

## Trades

- [ ] Offer/accept/reject/cancel/counter
- [ ] Commissioner review/veto if enabled
- [ ] Atomic processing
- [ ] Notifications and history

## Waivers

- [ ] Claims
- [ ] FAAB/priority
- [ ] Scheduled processing
- [ ] Failed-claim reasons
- [ ] Notifications

## Stats

- [ ] Provider sync jobs
- [ ] Freshness UI
- [ ] Payload validation
- [ ] Stale data warnings

## Players

- [ ] Player profile
- [ ] League-aware availability
- [ ] Ownership percentage
- [ ] Search/filter performance

## Projections

- [ ] Versioned projections
- [ ] Explanations
- [ ] Confidence/freshness
- [ ] Backtesting

## Injuries

- [ ] Injury history
- [ ] Source/freshness
- [ ] Alerts
- [ ] Projection impact

## Notifications

- [ ] Preferences
- [ ] Unread count
- [ ] Deep links
- [ ] Retry/dedupe

## Chat

- [ ] League messages
- [ ] Read state
- [ ] Moderation
- [ ] Rate limits

## Auth/Security

- [ ] CSRF for cookie flows
- [ ] Session management
- [ ] Reset/verification abuse tests
- [ ] Authorization matrix

## Frontend

- [ ] Mobile QA
- [ ] Loading/empty/error states
- [ ] Auth-expired handling
- [ ] Full e2e flows

## Ops

- [ ] Structured logs
- [ ] Metrics
- [ ] Error tracking
- [ ] Admin diagnostics
- [ ] Backup/restore tested
- [ ] Rollback plan

