# Alpha Open-PR Audit

Audited against `main` at `48153f7f9854efc27095d52d0efe629d751f8789` on 2026-08-21.

None of the open pull requests is safe to merge into the final hardening
branch. They remain open for historical review only; this audit does not
close, merge, or otherwise modify them.

| PR | Classification | Reason | Alpha disposition |
| --- | --- | --- | --- |
| [#116](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/116) | STALE / OPTIONAL | Draft-only ESPN identity import utility and test; current scoring and identity implementation landed later. | Do not merge. Re-evaluate as a narrowly scoped post-alpha data-quality change. |
| [#91](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/91) | SUPERSEDED | Earlier ESPN schedule-authority change predates the current durable scoring worker and verified schedule-window path. | Do not merge. |
| [#71](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/71) | UNSAFE / SUPERSEDED | Carries an obsolete career/rivalry implementation and a conflicting `0091` migration lineage. Current career and rivalry work is already on `main`. | Do not merge. |
| [#70](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/70) | UNSAFE / SUPERSEDED | Earlier ESPN shadow-scoring stack includes obsolete migrations and duplicate scoring paths. | Do not merge. |
| [#69](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/69) | UNSAFE / SUPERSEDED | Earlier production scoring hardening also contains obsolete `0091`/`0092` migrations and duplicate scoring implementation. | Do not merge. |
| [#67](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/67) | OPTIONAL / STALE | Vercel analytics is not an alpha launch requirement; GitHub reports a diff too large for safe last-minute incorporation. | Do not merge. |
| [#45](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/45) | STALE / RISKY | Older auth-entry navigation changes predate the current session and profile updates. | Do not merge. |
| [#35](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/35) | STALE / RISKY | Old beta shell, deployment, and navigation work overlaps later UI and runtime releases. | Do not merge. |
| [#31](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/31) | SUPERSEDED | Public-home UI predates current mobile shell and app routing. | Do not merge. |
| [#29](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/29) | OPTIONAL | Controlled player enrichment is not required to safely release current data; it needs a separate source-data audit. | Do not merge. |
| [#23](https://github.com/adamtheballer/College-Football-Fantasy-App/pull/23) | STALE / RISKY | Old release diagnostics/configuration overlaps current runtime provenance and deployment contracts. | Do not merge. |
