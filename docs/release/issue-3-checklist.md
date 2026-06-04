# Issue #3 Checklist — JWT Session and Refresh Hardening

- [x] Access token is JWT with short TTL and `sub`, `iat`, `exp` claims
- [x] Refresh sessions persisted with hashed opaque tokens
- [x] `/auth/signup` returns `access_token` and sets refresh cookie
- [x] `/auth/login` returns `access_token` and sets refresh cookie
- [x] `/auth/refresh` rotates refresh token and invalidates prior session
- [x] `/auth/logout` revokes active refresh session and clears cookie
- [x] Protected endpoints accept `Authorization: Bearer <token>`
- [x] Legacy `X-User-Token` path removed or explicitly deprecated for cutover
- [x] Frontend uses bearer auth and single retry after refresh
- [x] API tests cover login/signup/refresh/logout/revoked and expired token paths
- [x] Frontend tests cover bootstrap refresh and forced logout on refresh failure
