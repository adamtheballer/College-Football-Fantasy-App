import { describe, expect, it } from "vitest";

import { buildStandingsRows, formatDateTime, formatTradeAssets } from "./LeagueSettings";

describe("league settings trade history helpers", () => {
  it("renders complete trade asset details and preserves an empty-side fallback", () => {
    expect(formatTradeAssets([{ name: "Arch Manning", position: "QB", school: "Texas" }])).toEqual([
      "Arch Manning · QB · Texas",
    ]);
    expect(formatTradeAssets([])).toEqual(["No players listed"]);
  });

  it("uses a stable fallback when a completed trade has no valid timestamp", () => {
    expect(formatDateTime(null)).toBe("Unknown time");
    expect(formatDateTime("not-a-date")).toBe("Unknown time");
  });
});

describe("league settings standings helpers", () => {
  it("keeps calculated points against from the settings contract", () => {
    const rows = buildStandingsRows({
      standings: [{
        team_id: 1,
        team_name: "Emily's Team",
        wins: 2,
        losses: 0,
        ties: 0,
        points_for: 269.92,
        points_against: 211.8,
        rank: 1,
      }],
    } as never);

    expect(rows[0].points_for).toBe(269.92);
    expect(rows[0].points_against).toBe(211.8);
  });
});
