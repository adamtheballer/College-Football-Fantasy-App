# Final release-content classification

The current release scope contains 77 files and 298 tracked diff hunks.  The
CSV is the row-level source of truth and records every path, hunk count, area,
classification, reason, coverage, commit group, and preservation action.

| Classification | Files | Action |
| --- | ---: | --- |
| BETA_READY | 64 | Selectively stage and commit only after focused tests pass. |
| TEST_ONLY | 13 | Commit with the matching tested beta feature. |
| BETA_NEEDS_FIX | 0 | The draft lifecycle regression was corrected before this report. |
| POST_BETA / GENERATED / LOCAL_ONLY / SECRET / STALE / SUPERSEDED / MANUAL_REVIEW | 0 | No such release-scope hunk remains. |

No raw player-source CSV, access-code data, database backup, secret, cache,
virtual environment, or build output is part of this classification.  There is
therefore no non-release user work to place in the requested preservation stash.
The player-pool refresh remains separately blocked pending authoritative CSV
exports and is not represented by any staged or committed change.
