# Week 10 challenge publication — November 3, 2026

The owner requested current-week challenges and only the top three managers by points. Eight competitions were prepared, validated and published using existing services, with operator reasons and source verification in the audit ledger. They remain Upcoming until the existing Wednesday rollover on November 4 at 12:00 AM Eastern; they are not retroactively opened for Week 9. No user picks, account roles or championship award rules were changed.

## Published slate

| Competition | Games / pool | Entry deadline (Eastern) |
| --- | --- | --- |
| Slate 12 | 12 games; Miami at Notre Dame featured | November 7, 11:55 AM |
| Upset Hunter | 7 verified underdogs; frozen 1–5 point difficulty | November 7, 11:55 AM |
| Fantasy Five | 258 eligible players in 12 games | November 7, 11:55 AM |
| Lock of the Week | 12 games | November 7, 11:55 AM |
| Rivalry Duels | 5 common games | November 7, 11:55 AM |
| Fan Wars | 12 games; existing 67-school metadata | Each game at its kickoff |
| Fantasy Millionaire | 258 reviewed salaries in 12 games | November 7, 12:00 PM |
| Survivor | 12 games; existing series 1 | November 7, 12:00 PM |

The twelve games are Texas at Missouri, BYU at Utah, Oregon at Ohio State, Penn State at Washington, Alabama at LSU, Miami at Notre Dame, Georgia at Ole Miss, Oklahoma at Florida, Louisville at Georgia Tech, Michigan State at Michigan, Iowa State at Baylor, and Duke at NC State. Duels uses the first, second, third, fifth and sixth games.

Public ESPN scoreboards and exact event summaries were checked against canonical IDs, participants, scheduled states and kickoffs. Seven games exposed explicit provider underdog flags; only those are used for Upset Hunter. Existing difficulty policy uses the absolute published spread: up to 3 → 1, up to 7 → 2, up to 14 → 3, up to 21 → 4, above 21 → 5. No guessed betting line was substituted for the other five games.

Millionaire salaries follow the existing suggestion policy, `clamp(floor(0.8 * authoritative published projection + 0.5), 1, 30)`, reviewed against actual Week 10 forecasts. Every pool player has a real published forecast; a legal six-player formation fits 100 credits. Confirmed unavailable players were excluded before publication. Salary, player, game and scoring snapshots are frozen equally for all entrants.

Beat the Creator remains unpublished because there is no approved active creator or authorized pick set. The Week 8 sponsor was not copied into Week 10.

## Survivor publication gap

Week 9 had no Survivor instance and was never available for an enrolled manager to submit. Existing cancellation/settlement services recorded Week 9 as canceled with a reason and void-advanced the one existing enrollment. Its generated entry is explicitly `void`, with no selections, and its outcome is `void_advanced`. No prediction, win, championship award or enrollment was created. This preserves the original six-week series without penalizing an operator publication gap.

## Readback and display

All eight have publication timestamps and public state Upcoming. The lifecycle worker may store Fan Wars as processing before opening; its public state remains Upcoming until the configured entry time and week rollover. [Publication receipt, source evidence, salary inputs and readback](../../reports/challenges/2026-week10-publication.json).

The API and React leaderboard limits are now three, including weekly/season totals, per-challenge leaderboards, expanded manager standings and Fan Wars point standings. Ties preserve competition rank and stable ordering but do not expand the three-row cutoff. There are no outside-cutoff personal-rank rows or pagination controls. Legacy requests for larger result pages are capped on the server; offsets cannot expose fourth place or below. A read-only production check confirms all eight competitions become Open at the scheduled rollover. Point awards remain unchanged.

Validation: 109 challenge API tests passed (3 PostgreSQL-only skips locally); 62 availability tests; 701 React tests; all typechecks and production build; 13 production-build Playwright scenarios covering top-three behavior and mobile/desktop challenge flows. Required PostgreSQL and release CI remains the merge gate.
