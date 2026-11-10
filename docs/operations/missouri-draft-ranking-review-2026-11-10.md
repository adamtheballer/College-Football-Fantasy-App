# Missouri draft ranking review — November 10, 2026

The owner requested a substantial Ahmad Hardy demotion and a Jamal Roberts promotion on both the real and mock draft boards. The production baseline was Hardy **6 overall / RB5**, Roberts **356 overall / RB87**. Raw CFB27/source ranks and remaining projections still strongly favored Hardy; changing a source rank alone would be overridden by within-position projected-points ordering.

The existing shared backend master board now applies a 2026-only editorial RB order after model ordering and the valid-source-rank partition. Hardy cannot rank above RB60; Roberts cannot rank below RB15. A player already beyond the requested bound keeps that better/worse position respectively. Promoting Roberts may move Hardy another RB slot later. The current full-pool replay places Hardy around pick 200 and Roberts around pick 30; exact overall ranks depend on league settings and the selected conference pool.

Only a unique exact normalized name, Missouri school and RB position may match. Ambiguous identities are skipped. Unranked players remain in the unranked bucket. Small conference pools clamp safely to their available RB slots. The review expires with the 2026 season and does not follow transfers. Other-position slots and the relative ordering of other RBs remain unchanged.

Both React rooms, real server auto-pick and backend mock auto-pick already consume `build_draft_ranking_snapshot`; no second client ranking exception was added. The versioned cache includes season and the policy revision changes, so a refresh cannot retain the old order or reuse the 2026 review in another season. Search/position filters retain the global master rank. Explicit points and observed-ADP sorts keep their existing meanings.

This changes editorial priority only. It does not change injury designations, actual stats, published projections, source ADP, CFB27 ratings, ownership, deliberate queues or existing picks. Forecast values and model scores remain intact.

Role context: [Missouri offense and Hardy's return](https://www.si.com/college/missouri/football/how-ahmad-hardy-changes-mizzou-s-offense-vs-texas), [November 7 depth chart](https://www.ourlads.com/ncaa-football-depth-charts/depth-chart/missouri/91234). The owner-selected draft priorities are editorial decisions, not a claim that either source publishes these fantasy ranks.

Validation covers the full 815-player fixture, deterministic order, continuous unique ranks, unchanged forecasts/talent/model scores, preserved other-position slots and other RB order, future seasons/transfers/unranked identities, ambiguous names, small pools, shared real/mock snapshots, API filtering and explicit points sorting.
