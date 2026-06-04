# Feature: Homepage Transfer Wire

## Summary

Replace the logged-in homepage Game Plan / Ready Board block with a fantasy-relevant College Football News and Transfer Wire experience.

## Problem

- The current homepage guidance card is generic and does not surface actionable fantasy context.
- College football fantasy managers need fast visibility into transfers, injuries, depth chart movement, eligibility, and coaching changes.
- External news ingestion must be safe, source-attributed, and non-blocking.

## Story 1: Safe News Storage

As a logged-in fantasy manager, I want news items stored separately from notifications so the homepage can show transfer and injury context without coupling to alerts.

Acceptance criteria:

- News items persist source metadata, category, status, detected player/team context, relevance score, and fantasy impact.
- News sources persist polling metadata and failures.
- Hidden and duplicate news items are not shown in the public feed.
- No news ingestion writes real league draft or roster records.

## Story 2: College Football News Provider

As the app, I want to ingest College Football News safely so users can read fantasy-relevant headlines while the original source receives attribution and traffic.

Acceptance criteria:

- Provider tries RSS/feed URLs before homepage/index metadata.
- Provider extracts headlines, links, summaries/excerpts, published dates, and metadata only.
- Provider does not fetch full article pages, bypass protections, copy full articles, or run from the frontend.
- Source failures are captured and do not break app startup or homepage rendering.

## Story 3: Classification And Relevance

As a fantasy manager, I want the homepage to prioritize transfer, injury, depth chart, eligibility, and role-change news instead of generic previews.

Acceptance criteria:

- Transfer, injury, depth chart, eligibility, coaching, NFL Draft, rankings, team news, and general categories are classified deterministically.
- Fantasy relevance scores prioritize injuries and transfer/role movement above generic previews.
- Player/team matching never creates Player rows and only assigns player IDs on safe matches.
- Fantasy impact language is framed as monitoring guidance, not fabricated certainty.

## Story 4: News API

As the frontend, I want stable news endpoints so the homepage can render the Transfer Wire independently of notifications.

Acceptance criteria:

- `GET /news/feed` supports category, team, player, position, pagination, minimum relevance, and breaking filters.
- `GET /news/breaking` returns recent high-relevance items.
- `GET /news/transfers` returns transfer items.
- `POST /news/manual` supports manual fallback creation.
- `POST /news/ingest` supports manual development ingestion.

## Story 5: Homepage Transfer Wire UI

As a logged-in fantasy manager, I want a Transfer Wire card on the homepage so I can scan relevant movement before checking leagues or drafts.

Acceptance criteria:

- Game Plan / Ready Board is removed from the homepage.
- Transfer Wire appears before stat cards and does not remove Resume League, stat cards, Your Leagues, Upcoming Drafts, or League Alerts.
- Tabs include Breaking, Transfers, Injuries, and Team News.
- Each item shows category, headline, fantasy impact, metadata, source attribution, relative time, relevance label, and source link.
- Loading, empty, and API error states are handled without failing the homepage.

## Manual Verification

- Run the news source seed script.
- Run the news sync script with `--dry-run` first, then without dry-run when source access is available.
- Add a manual transfer and injury item through `POST /news/manual`.
- Confirm the logged-in homepage renders Transfer Wire and still renders if `/news/feed` fails.
