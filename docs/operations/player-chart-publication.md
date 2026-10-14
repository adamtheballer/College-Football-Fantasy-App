# Player chart publication — combined New Build preparation

Updated October 14, 2026. Implementation is local on the existing combined branch. **No push, merge, production migration/backfill, deployment, native app build, TestFlight upload or App Store release.** Local web builds and disposable database tests are verification artifacts.

## Confirmed causes and measured evidence

- The old trajectory reader required a provider FPTS field instead of scoring verified raw categories, read live league scores without whole-week finality, and returned multiple historical/future forecasts. This left completed games dotted or missing. Standalone unrostered history lacked a durable publication path.
- Historical value serialization reused mutable current-player fields. Week-specific values and metadata could therefore flatten or move when a newer value was calculated. The trajectory's separate percentile fallback was not the value service's formula.
- Weekly value calculations mixed weekly forecasts with season-total peers, normalized against database rows outside the approved game catalog, issued repeated peer-stat queries, and could stop at the first failed player. Older repairs could replace newer current values; a prior-season calculation week could block current-season initialization. Week 12+ incorrectly reused Week 11 weights.
- Outlook refresh returned before historical publication when the next schedule was unavailable or after Week 13. Provider Week 0 selection was not shared by chart/value/outlook calculations, allowing the wrong opening game to be selected.
- Matchup certification checks starters. Its finished-matchup flags alone can precede an unrostered player's late game. The shared finality guard now additionally rejects known unfinished, canceled, postponed or ambiguous catalog games, using the same game selection as scoring. Missing source/schedule evidence still requires the release audit; a calendar date does not establish finality.
- Completed-week comparisons could use a later projection as an original forecast. Any non-null value input context was treated as finalization proof. Chart keys included array indexes, actual-only tooltips invented comparisons, and value tooltips rounded 57.2 to 57.

The public read-only audit successfully fetched **815/815** current catalog charts: **zero players had actual points**, all 815 retained multiple forecasts, and all lacked the new finality field. Values were present only at Weeks 1 and 3 (815 each; 1,630 weekly points). Alex Perry's response had Week 1–6 forecasts and equal displayed Week 1/3 values of 67.8. That equality is not by itself proof of a formula error; original database rows/inputs must be inspected. The fully paginated public catalog was independently checked and contained the same 815 IDs.

Evidence: `player-chart-audit-2026-10-14.json`. This captures public responses, not privileged source-stat or matchup certification. Production remains unchanged by this work.

## Data flow and files

| Stage | Implementation and responsibility |
|---|---|
| Forecast generation | `api/app/services/projections/engine.py`: existing usage/efficiency, talent, team environment, opponent defense and availability model; existing standard scoring engine converts categories to FPTS. |
| Conservative updates | `weekly_outlook_refresh.py`: existing 65/35 initial preseason/postgame blend, 12% capped performance residual and 15% initial drift limit remain intact. OUT/BYE rules take precedence. Existing published-version priority remains authoritative. |
| Statistics | Existing accepted ESPN normalization/promotion writes canonical `PlayerStat` and final `PlayerGameStat`. Chart recovery can use an exact selected game's `espn_final_boxscore` fact when the weekly row is missing, without writing weekly stats or league results. |
| Game/week selection | `fantasy_game_selection.py`: one scoring game per school; a qualifying completed Week 0 opener supplies fantasy Week 1. Charts, values and outlook now share this mapping. |
| Finality | `fantasy_week_finality.py`: every persisted matchup must be final/stat-corrected, and known selected catalog games must be final. Delayed/ambiguous games cannot publish live history. Durable publication records preserve earlier certified history. |
| Pregame archive | `chart_forecasts.py`, `PlayerChartForecast`, migration **0121**: stable player/season/fantasy-week snapshot with original raw forecast categories, position, standard points, source projection ID/version, publication/kickoff timestamps and capture time. |
| Actual archive | `player_chart_publication.py`, `PlayerChartWeek`, migration **0119**: unique player/season/week raw facts, frozen position/rules, standard score, source reference, input hash, calculation version and finalization time. |
| Value archive | `player_trade_value.py`, `PlayerTradeValue.input_context_json`, migration **0119**: existing weekly policy rows plus retained weights, baseline/future/availability/scarcity inputs, peer IDs/positions, scoring rules and cutoff. New input version is `weekly-stats-projections-v4-cutoff-eligible`; formula policy remains `universal_v2`. |
| Audit | `PlayerChartPublicationRun`: complete/partial coverage, missing IDs, per-player failures, prior/new corrections, recomputed flat values and input/output fingerprints. |
| Worker trigger | `espn_live_scoring.py`: captures started-game forecasts after the public-scoring readiness gate; post-final outlook publishes actuals and values before next-schedule checks, including Week 13. Week 0 capture occurs before its performance changes Week 1 outlooks. |
| API | `api/routes/players.py`, `schemas/player_trajectory.py`: explicit season/week, finality, separate actual/forecast fields, valid weekly values and selected-league context. Reads never create chart records. |
| UI | `web/client/hooks/use-players.ts`, shared `PlayerCardModal.tsx` and `PlayerTrajectoryChart.tsx`: every card caller uses the same trajectory. Query keys and abort signals protect player/season/league ownership; responses without authoritative finality are rejected. |
| Repair tools | `scripts/backfill_player_charts.py`, `audit_public_player_charts.py`, `certify_player_chart_migration.py`: read-only audit, guarded local repair, public inventory coverage, and disposable migration certification. |

P4/Notre Dame QB/RB/WR/TE/K players are processed through keyset batches, including unrostered, injured and unviewed players. Generated/retired canonical records do not enter new game-catalog calculations. New value snapshots use this same eligible catalog for positional peers; saved historical peer lists remain unchanged during corrections. Player-card viewing is never a prerequisite.

`PlayerHistoricalGameStat` from the separate stats task retains verified prior-year game logs. A 2025 FIU game for Alex Perry is not copied into a 2026 fantasy-week chart. Current chart defaults come from the configured backend football season, independently of the game-log year or calendar-year rollover.

## Existing value formula and cutoff contract

The authoritative policies remain `cfb27_exact_preseason_v1` and `universal_v2`. Before authoritative Week 1 completion, value is approved raw CFB27 rating × the existing official-availability multiplier, normalized to **0–99**. Missing approved ratings are unavailable. The graph now shares this availability-adjusted policy with the card instead of displaying an unadjusted/stale baseline.

In season, let `r` be rating percentile, `p` verified cumulative standard-scoring mean-performance percentile, `f` forecast percentile, `a` availability score and `s` position scarcity. With weekly rating/performance/future weights `R/P/F`, the existing seven factors are:

```text
preseasonRating    = round2(R * r)
seasonPerformance  = round2(P * .70 * p)
recentForm         = round2(P * .30 * p)
futureProjection   = round2(F * .65 * f)
usageRole          = round2(F * .20 * f)
availability       = round2(F * .10 * a)
positionalScarcity = round2(F * .05 * s)
value              = round1(clamp(sum(seven rounded factors), 0, 99))
```

The existing recentForm/seasonPerformance factors both use the cumulative percentile; this work does not invent a recent-games formula. Future/usage factors share the existing forecast percentile.

| Week | R | P | F |
|---|---:|---:|---:|
| 1 | .75 | .15 | .10 |
| 2 | .65 | .25 | .10 |
| 3 | .55 | .35 | .10 |
| 4 | .45 | .45 | .10 |
| 5 | .375 | .50 | .125 |
| 6 | .30 | .55 | .15 |
| 7 | .275 | .60 | .125 |
| 8 | .25 | .625 | .125 |
| 9 | .20 | .65 | .15 |
| 10 | 1/6 | 41/60 | .15 |
| 11 | 2/15 | 43/60 | .15 |
| 12–13 | .10 | .75 | .15 |

Percentile is `100 * count(peer values <= own value) / peer count`. Weekly forecasts compare with weekly peer forecasts; a season-total fallback compares with peer season totals. Missing performance/future inputs fall back to the rating percentile; missing percentile inputs retain the existing 35 fallback. Existing confidence uses rating presence (.45 if missing) × availability confidence. These fallback calculations are not evidence of actual fantasy production.

Existing availability scores/confidence are ACTIVE 100/1, QUESTIONABLE 82/.85, DOUBTFUL 55/.7, OUT 30/.7, SUSPENDED 20/.65 and UNKNOWN 70/.55. Canonical FULL resolves to ACTIVE, and season-out/inactive/IR designations resolve to the existing OUT category. Scarcity remains QB 38, RB 58, WR 55, TE 62 and K 25. No weights or scarcity values were invented.

Only finalized or durably published current-season facts through the cutoff contribute; live and future weeks are excluded. Stored actual rules/positions survive corrections. New value contexts freeze non-statistical inputs, peer identities/positions, weights and rules. Historical corrections recalculate supported statistical inputs using the retained context. Older missing cutoffs are refused, including gaps before a later finalized week and prior seasons without saved inputs. A past-season preseason row can be retained but cannot be rebuilt from the current rating catalog.

A source change that produces the same result records a real recomputation, not an assumed successful flat line. The Week 6 regression independently expects factors 15, 19.25, 8.25, 9.75, 3, 1.5 and .41, totaling **57.2** after normalization. History uses each row's value; newer current values and current-season initialization survive older repairs.

## Display and refresh rules

- Finalized actuals remain under their original weeks and render solid blue. A game ending alone is insufficient. Value history also renders solid blue.
- Only the upcoming unfinished forecast is white/dotted. An adjacent last actual is a drawing anchor, not another forecast record. Original pregame comparisons stay separate from actuals.
- Forecast capture accepts a source timestamp at/before canonical kickoff. Known postponed/canceled games are not frozen at an expired deadline. Missing kickoff evidence or original inputs remain unavailable; later estimates are never called original forecasts.
- Earlier unfinished weeks are gaps while the upcoming forecast advances after the latest known finalized week. Missing finalized stats and awaiting-finality gaps have different labels. Byes remain explicit gaps. Paths do not bridge missing weeks.
- Confirmed zero and negative scores remain valid. Missing/unverified/unrecognized/non-finite or explicitly incomplete inputs are not converted to zero. FPTS-only legacy data supports standard history, not unsupported custom-league rescoring.
- Selected-league actuals/forecasts use its settings; standalone charts explicitly label standard CFFB scoring. Universal market value intentionally uses standard scoring.
- Polling/focus refreshes retain player, tab, selected week and scroll. Stable week keys survive insertion and projected-to-final transitions. Older requests are aborted; mismatched player/season/league replies and unproven/live actual totals are rejected. Refresh errors retain last loaded data with a visible status. Value tooltips retain decimal precision and show the week/metric.

## Coverage and verification

| Environment | Before | After / result |
|---|---|---|
| Public production, read-only | 815 current players, 0 with actual chart points, 1,630 value points at Weeks 1/3 only | Same production data; no repair writes/deployment. All 815 IDs independently matched current paginated catalog. |
| Owned local source-backed database | 816 eligible records including one fixture, no finalized weeks, zero weekly chart snapshots | No actual/value records fabricated. Additive migration 0121 installed locally; final read-only audit retained zero weekly records. |
| Isolated synthetic full catalog | 815 unrostered players, no snapshots | 815 evidenced forecasts, 815 actuals and 815 calculated values; all five positions, multiple batches, idempotent reruns and a supported correction. |
| Isolated CLI repair | Five supported position examples, zero chart rows | Five actual/value snapshots; repeat repair retained five unique records. |

Final verification:

- Backend chart/value/outlook plus existing fantasy-game/scoring/season-rank regressions: **109 passed**, including catalog games that outlast starter matchups, accepted final-game recovery without weekly/stat/standing mutations, postponed forecasts and past-season value refusal.
- PostgreSQL final chart/value/outlook suite: **55 passed**. Migration certificate results are recorded in the checklist. Migrations 0119/0121 preserve existing records, do not backfill implicitly, permit unused rollback, reject destructive rollback after actual/pregame history exists, and match ORM metadata.
- React: **601 passed across 95 files**. TypeScript and local web artifact build passed.
- Chromium at **1280px and 390px: 2 passed**, using explicitly synthetic trajectory responses and a synthetic shell session, with real public local card data. Week 6 18.4 / Week 7 21.2 → 24.6 / Week 8 own forecast, color/line state, tooltip, selected-week and scroll persistence were verified. Screenshots were inspected. This is browser verification, not physical-iPhone testing or provider completeness.
- Actual public local API check passed configured/current-versus-prior-season behavior, no invented actuals and no prior-season baseline leakage.

## Staged repair and combined rollout

During the release hold, the CLI is read-only unless `--apply-local` explicitly targets an owned isolated localhost/SQLite database:

```sh
PYTHONPATH=. python scripts/backfill_player_charts.py --database-url <explicit-database-url> --season 2026
```

Audit output identifies finalized weeks, eligible IDs, supported source actuals, missing source/actual/value IDs, unavailable original forecasts, unrecoverable value cutoffs and before/after counts. The apply path preserves valid rows and records corrections. It writes chart/value snapshots only; accepted per-game recovery does not change weekly statistics, matchup results or standings. Unknown source data remains a gap.

Once the complete New Build list is finished and the owner explicitly authorizes release:

1. Backup and certify the complete migration chain through 0121, including existing retained history.
2. Privileged read-only audit: confirm real weekly certification, complete catalog schedules/provider games, stable identity/season/game mapping and raw statistical provenance. Public API results cannot establish these facts.
3. Recover only evidenced raw actuals and historical value/forecast inputs. Keep unavailable legacy cutoffs as reported gaps; do not repeat current values across old weeks or infer zero from absence.
4. Deploy compatible API/worker/React together; the new client requires explicit weekly finality. Review the dry-run manifest before the separately authorized production repair. The current CLI deliberately refuses non-local apply under this hold.
5. Run targeted supported repairs through the existing publication services, compare coverage/corrections, and verify no undocumented score/standing changes. Retain chart and pregame history on application rollback.
6. Bundle the confirmed web UI into the eventual combined native build, then perform signed physical-iPhone UI/notification verification and release only after explicit authorization.

Production raw-stat/finality validation, original missing historical contexts and physical-iPhone verification remain outstanding. The local code and synthetic coverage do not establish that production history has been repaired.
