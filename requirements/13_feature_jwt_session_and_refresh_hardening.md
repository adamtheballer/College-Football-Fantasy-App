# Feature: JWT Session and Refresh Token Hardening

## Description
Replace the current long-lived API token model with a simple, more secure session architecture based on short-lived JWT access tokens and rotating refresh tokens. The React app should refresh sessions automatically without forcing frequent re-login, while backend routes should stop trusting static bearer secrets stored indefinitely in local storage.

## In Scope
- Replace `api_token` request authentication with JWT access tokens
- Add refresh-token based session renewal
- Rotate refresh tokens on use and revoke them on logout
- Migrate the React app from `X-User-Token` to `Authorization: Bearer <jwt>`
- Add frontend refresh handling so the UI can recover from access-token expiry
- Add backend session tables, config, and tests for the new auth flow

## Out of Scope
- Third-party identity providers such as Google, Apple, or GitHub OAuth
- Multi-factor authentication
- Full enterprise session management across multiple products

## User Stories
- As a signed-in user, I stay logged in across normal app usage without carrying a permanent static token.
- As a security-conscious team, we can expire access tokens quickly and revoke refresh sessions on logout or compromise.
- As an engineer, I can reason about a standard auth flow with explicit token expiry and refresh behavior instead of long-lived header secrets.

## Acceptance Criteria
- Login and signup return a short-lived JWT access token instead of the current durable `api_token`.
- Access tokens expire on a short window.
  - Recommended: 10 to 15 minutes.
- Refresh tokens are separate from access tokens and are not valid indefinitely.
  - Recommended: 7 to 30 days.
- Refresh tokens are rotated on each successful refresh and the previous token is invalidated.
- Backend auth dependencies validate JWT signature, expiry, and subject claims instead of looking up a raw token string.
- React sends access tokens using the `Authorization` header, not `X-User-Token`.
- React automatically refreshes the session before or immediately after access-token expiry and retries the original request once.
- Logout revokes the active refresh session and clears client auth state.
- Backend supports explicit unauthorized responses for:
  - missing token
  - expired access token
  - invalid access token
  - expired refresh token
  - revoked refresh token
- Existing protected routes continue to work after migration.

## Workflow
1. Add JWT signing and verification utilities plus refresh-token persistence.
2. Introduce login, signup, refresh, and logout contracts for the new session flow.
3. Update backend auth dependencies to read `Authorization: Bearer` access tokens.
4. Add React token storage, refresh orchestration, and single-retry request handling.
5. Remove or deprecate the old `api_token` and `X-User-Token` flow after the React client is migrated.
6. Add API and frontend tests for login, refresh, expiry, logout, and revoked session behavior.

## API Specs
- `POST /auth/signup`
  - Response:
    - `access_token`
    - `access_token_expires_at`
    - `user`
  - Refresh token should be set as an `HttpOnly` cookie.
- `POST /auth/login`
  - Response:
    - `access_token`
    - `access_token_expires_at`
    - `user`
  - Refresh token should be set as an `HttpOnly` cookie.
- `POST /auth/refresh`
  - Reads the refresh token from cookie or explicit refresh credential transport
  - Response:
    - new `access_token`
    - new `access_token_expires_at`
  - Rotates refresh token and invalidates the previous token
- `POST /auth/logout`
  - Revokes the current refresh session
  - Clears refresh cookie
- Protected routes
  - Require `Authorization: Bearer <access_token>`
  - During migration, old `X-User-Token` support may remain temporarily but should be marked deprecated and removed after React is cut over

## UI Specs
- React auth provider should store the access token with explicit expiry metadata
- Preferred implementation:
  - keep refresh token in `HttpOnly` cookie
  - keep access token in memory and mirror to storage only if needed for reload bootstrap
- The API client should:
  - attach `Authorization` header
  - detect `401` from expired access token
  - call `/auth/refresh`
  - retry the original request once after successful refresh
  - clear auth and redirect to login if refresh fails
- Bootstrap behavior:
  - on app load, attempt to restore access token if still valid
  - if missing or expired but refresh cookie exists, call `/auth/refresh` once
- UI error handling:
  - distinguish bad credentials from expired session
  - show “session expired” messaging when refresh fails and re-auth is required

## Database Specs
- Table: `refresh_sessions`
  - Columns:
    - `id`
    - `user_id`
    - `token_hash`
    - `issued_at`
    - `expires_at`
    - `rotated_from_session_id` nullable
    - `revoked_at` nullable
    - `last_used_at` nullable
    - optional `user_agent`
    - optional `ip_address`
- Indexes:
  - `refresh_sessions (user_id, revoked_at)`
  - `refresh_sessions (expires_at)`
- Do not persist raw refresh tokens; persist only a hash

## Technical Notes
- Recommended implementation details
  - Use one server-side signing secret from config for JWT access tokens
  - Access token claims should include:
    - `sub` as user ID
    - `exp`
    - `iat`
    - optional `email`
  - Refresh token should be an opaque random secret, not another long-lived JWT
  - Hash refresh tokens before storing them
  - Rotate refresh tokens on every successful `/auth/refresh`
  - Revoke the current refresh session on logout
- Config additions
  - `JWT_SECRET_KEY`
  - `JWT_ACCESS_TOKEN_TTL_MINUTES`
  - `REFRESH_TOKEN_TTL_DAYS`
  - `REFRESH_COOKIE_NAME`
  - `REFRESH_COOKIE_SECURE`
  - `REFRESH_COOKIE_SAMESITE`
- Backend file targets
  - `api/app/api/routes/auth.py`
  - `api/app/api/deps.py`
  - `api/app/core/security.py`
  - `api/app/models/user.py`
  - new session model and migration files
- Frontend file targets
  - `web/client/hooks/use-auth.tsx`
  - `web/client/lib/api.ts`
  - protected route/session bootstrap flows under `web/client/`

## Rollout Notes
- Phase 1
  - Add JWT access-token issuance and refresh-session persistence
  - Keep legacy token auth temporarily for compatibility
- Phase 2
  - Migrate React to bearer auth plus refresh flow
  - Validate protected pages and request retry behavior
- Phase 3
  - Remove legacy `api_token` auth and `X-User-Token`
  - Remove obsolete user token fields if no longer needed
- Testing
  - Add API tests for:
    - signup
    - login
    - refresh
    - expired access token
    - revoked refresh token
    - logout
  - Add frontend tests for:
    - bootstrap refresh
    - single retry after `401`
    - forced logout on refresh failure
