# League Chat System

## Current behavior

`league_messages` stores flat system events only. There are no chat threads, direct conversations, read cursors, message endpoints, or unread-count APIs. `Chats.tsx` renders league activity and placeholder cards. Trade acceptance and commissioner approval currently create generic `league_messages` rows.

## Target behavior

Every league owns one `league` chat thread. Direct threads are bound to a league and normalized by their two participant user IDs, allowing the same pair to have distinct conversations in different leagues. The API validates active league membership for every read and write. Removed users lose access immediately, while messages remain for league history.

## Migration approach

The migration creates `chat_threads`, `chat_thread_participants`, `chat_messages`, and `chat_read_states`. It creates one master thread per existing league, imports every legacy `league_messages` record into that thread, and records the legacy row ID plus the original message type in `metadata_json`. Legacy `trade` types are normalized to `trade_processed`; all other unsupported legacy types become `system`. It preserves the legacy table until a later, explicitly approved retirement migration and verifies the total imported row count before completing. New leagues create their master thread in the same transaction as the league.

## API surface

- `GET /leagues/{league_id}/chats`
- `POST /leagues/{league_id}/chats/direct` with `{ "recipient_user_id": 123 }`
- `GET /leagues/{league_id}/chats/{thread_id}/messages`
- `POST /leagues/{league_id}/chats/{thread_id}/messages`
- `PATCH /leagues/{league_id}/chats/{thread_id}/messages/{message_id}`
- `DELETE /leagues/{league_id}/chats/{thread_id}/messages/{message_id}`
- `POST /leagues/{league_id}/chats/{thread_id}/read`
- `GET /chats/unread-summary`

Messages use cursor pagination. User messages are plain text, capped at 2,000 characters, and accept a per-sender `client_message_id` to make retries idempotent. Users can edit only their own messages during the configured 15-minute window and can soft-delete their own messages. Commissioners can moderate user messages, while system and trade audit messages are immutable through the public API. Every direct-thread creation, commissioner deletion, trade announcement, and league-member removal is recorded in `chat_audit_events`.

## Security and abuse controls

Every endpoint requires authentication, active league membership, a matching league/thread pair, and direct-thread participation where applicable. Unauthorized direct-thread requests return `404` rather than revealing a private thread. Message, direct-thread, and read actions use server-side per-user rate-limit events; the request IP is retained only as a hashed audit signal, so managers sharing a connection do not consume one another's allowance. Defaults are 30 messages per minute plus 120 per 15 minutes, 20 new direct threads per hour, and 120 read updates per minute. The UI only renders React-escaped plain text; the API rejects markup, unsupported control characters, empty content, and bodies above 2,000 characters.

## Unread and update strategy

`chat_read_states` stores one read cursor per user/thread. Unread totals count messages after that cursor while excluding messages sent by the reader. While a thread is open, the client polls `GET .../messages?after_message_id={last_known_id}` every five seconds and merges only new rows into its cached history. Away from Chats, the app polls only `GET /chats/unread-summary` every ten seconds. Both polling paths pause while the document is hidden and refetch on focus. No chat state is persisted solely in browser storage. The schema and cursor contract support a future websocket or SSE fan-out without changing authorization or storage rules.

## Trade finalization

Trade announcements are written with an idempotency event key of `trade:{trade_offer_id}:finalized`. A no-review offer announces when the receiving manager accepts it; a commissioner-review offer announces only when the commissioner approves it. A delayed roster transfer updates the original announcement to `processed` instead of posting another finalized event.
