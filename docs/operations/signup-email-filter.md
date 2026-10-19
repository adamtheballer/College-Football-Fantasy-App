# Signup email filter

`POST /auth/signup` enforces email policy on the server, including native apps
and direct API requests. Existing sign-in, refresh and password-reset flows
retain their previous account lookup behavior.

The policy rejects malformed addresses (including addresses longer than the
database's 200-character limit), known disposable providers and their
subdomains, and definitive DNS evidence that a domain cannot receive mail
(NXDOMAIN, null MX, or no usable mail routing). Regular custom domains, school
addresses, plus aliases and Apple private relay addresses remain supported.
SMTP A/AAAA fallback is supported by `email-validator` when appropriate.

Disposable domains are bundled in the locked `disposable-email-domains`
dependency: https://github.com/disposable-email-domains/python-disposable-email-domains.
Update it with `uv lock --upgrade-package disposable-email-domains`, review the
lockfile, run the signup tests, and deploy. No runtime blocklist download or
third-party mailbox-verification API receives users' addresses.

DNS checks have a three-second total budget across queries and a bounded
2,048-entry DNS cache honoring TTLs. Temporary DNS failures return 503 with
`Retry-After: 30`; they neither create accounts nor permanently mark an address
invalid. Address policy errors return 422 with a readable `detail` supported
by the existing signup UI. Rejected policy attempts count toward the existing
five-per-15-minute signup limit by IP/address. Attempts are committed before
policy validation, moderation, or optional Early Access reservation mutation.

Settings:

- `SIGNUP_EMAIL_CHECK_DELIVERABILITY=true`: keep enabled in production. Only
  isolated offline tests using synthetic addresses disable DNS. Syntax and
  disposable checks still apply. Reserved `.test` domains are accepted only in
  the server-configured `ENVIRONMENT=e2e` test environment.
- `SIGNUP_EMAIL_DNS_TIMEOUT_SECONDS=3`: total DNS budget, constrained to 0.1–10.
- `SIGNUP_EMAIL_BLOCKED_DOMAINS`: comma-separated operator blocks, with label
  boundary/subdomain matching.
- `SIGNUP_EMAIL_ALLOWED_DOMAINS`: overrides disposable-list false positives,
  including subdomains. Explicit operator blocks win; syntax/DNS always apply.

This does **not** establish ownership of a mailbox or detect invented local
parts at Gmail or another real provider. The public beta still intentionally
does not send verification mail, and its legacy `email_verified_at` field is
not proof of inbox ownership. Blocking that class of fake account requires a
separate email-confirmation rollout with an approved sender. Do not silently
enable outbound mail or delete existing accounts as part of this filter.

Verification: `PYTHONPATH=. uv run pytest -q tests/api/test_signup_email_policy.py
tests/api/test_auth_sessions.py tests/api/test_beta_access.py`. Policy tests use
DNS records/exceptions without network calls. For production smoke checks, use
only rejected disposable/reserved addresses and confirm no account/session was
created; do not create fake accounts on real providers.
