# Feature: Push Alerts and Notification Controls

## Summary

Add production-grade web push notifications with per-user and per-league preferences for injuries, big plays, and usage/projection events.

## Problem

- Notifications exist but need stronger preference control, reliable delivery tracking, and clear trigger taxonomy.
- Users need contextual alerts that are useful and not spammy.

## Scope

### Subscription and Opt-In

- Trigger push permission prompt after meaningful action (not first page load).
- Persist web push subscriptions by user/device.
- Support revoke/refresh token lifecycle.

### Preference Controls

- Global push on/off.
- Per-league push on/off.
- Category toggles:
  - injury/status alerts
  - big play / TD alerts
  - projection/usage/boom alerts
- Quiet-time/volume controls as configurable policy.

### Trigger Engine

Generate notification events for:

- injury status change for rostered player
- big play events (feed-dependent)
- matchup swing thresholds

### Delivery Pipeline

- Queue outgoing notifications.
- Track status (`pending`, `delivered`, `failed`) and attempts.
- Retry bounded failures with diagnostics/audit logs.
- Respect preference and league filters before enqueue.

## Acceptance Criteria

- Eligible users receive alerts for enabled categories only.
- Disabled categories and league-level opt-out suppress sends.
- Delivery attempts and failures are traceable.
- Message payloads include actionable context (player, league, impact).
