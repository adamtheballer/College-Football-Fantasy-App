import { describe, expect, it } from "vitest";

import {
  buildScorePreviewRows,
  buildStatPreviewRows,
  numberOrUndefined,
  parseJsonObject,
} from "./AdminScoring";

describe("AdminScoring helpers", () => {
  it("turns correction preview scores into readable delta rows", () => {
    const rows = buildScorePreviewRows({
      player_id: 10,
      season: 2026,
      week: 1,
      affected_league_ids: [7, 8],
      before_stats: { PassingYards: 200 },
      after_stats: { PassingYards: 300 },
      before_scores: { "7": 20, "8": null },
      projected_scores: { "7": 28, "8": 18 },
    });

    expect(rows).toEqual([
      { leagueId: 7, before: 20, after: 28, delta: 8 },
      { leagueId: 8, before: null, after: 18, delta: null },
    ]);
  });

  it("turns corrected stats into before and after rows without raw JSON as the primary UI", () => {
    const rows = buildStatPreviewRows({
      player_id: 10,
      season: 2026,
      week: 1,
      affected_league_ids: [7],
      before_stats: { PassingTouchdowns: 2 },
      after_stats: { PassingTouchdowns: 4, PassingYards: 300 },
      before_scores: { "7": 20 },
      projected_scores: { "7": 28 },
    });

    expect(rows).toEqual([
      { key: "PassingTouchdowns", before: "2.0", after: "4.0" },
      { key: "PassingYards", before: "—", after: "300.0" },
    ]);
  });

  it("validates admin numeric and stats inputs", () => {
    expect(numberOrUndefined("42")).toBe(42);
    expect(numberOrUndefined("")).toBeUndefined();
    expect(parseJsonObject('{"PassingYards":300}')).toEqual({ PassingYards: 300 });
    expect(() => parseJsonObject("[]")).toThrow("Stats must be a JSON object.");
  });
});
