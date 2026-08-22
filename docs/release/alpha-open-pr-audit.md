# Alpha Open Pull Request Audit

Baseline inspected: `main` at `14a1a95f2eea6aeb84b25dc9d3d48fe817e81556` on 2026-08-21.

The release candidate is the single integration point. Older draft pull requests
must not be merged merely because they contain a passing historical check.

| PR | Classification | Release disposition |
| --- | --- | --- |
| #161 — Final alpha certification | ALPHA REQUIRED | Canonical draft RC. It contains the current repaired implementation and is the only candidate for a future `main` merge. |
| #160 — League playoffs | ALREADY INCLUDED | Its current approved work is already incorporated in the RC ancestry. The original `verify` failure is repaired in the RC, not by merging the stale PR head. |
| #155 | ALREADY INCLUDED | Included by the RC ancestry; do not merge separately. |
| #154 | SUPERSEDED | The intended provider-disclosure navigation removal remains, while the required public direct route was restored in the RC. |
| #116 | STALE | Superseded by later current route, mobile, and certification work. |
| #91 | SUPERSEDED | Later career/profile implementation is canonical. |
| #71 | UNSAFE | Historical CI failures and stale integration assumptions make it unsuitable for release merge. |
| #70 | UNSAFE | Historical CI failures and stale integration assumptions make it unsuitable for release merge. |
| #69 | UNSAFE | Old migration/integration work must not be imported into the current Alembic chain. |
| #45 | STALE | Historical test/runtime failure and later superseding work. |
| #35 | STALE | Old work superseded by the current implementation. |
| #31 | SUPERSEDED | Replaced by later canonical UI/workflow changes. |
| #29 | OPTIONAL | Not alpha-required; defer until after the release freeze. |
| #23 | STALE | Historical work no longer matches the current architecture. |

After a successful RC merge and deployment verification, close or archive each
non-canonical draft with a link to the merged RC. This avoids accidentally
reintroducing retired implementations of live scoring, Rival Week, profile
state, navigation, or player enrichment.
