import { describe, expect, it } from "vitest";

import {
  getHistoricalStatColumnsForPosition,
  historicalStatValuesForSeason,
  historicalStatsTablePosition,
} from "./historicalStatColumns";

const allColumns = [
  "Pass Yds", "Pass TD", "INT", "Comp", "Pass Att", "Rush Att", "Rush Yds", "Rush TD",
  "Receptions", "Rec Yds", "Rec TD", "Targets", "Fumbles", "FGM", "FGA", "FG%", "XPM", "XPA",
];

describe("historical position-aware stat columns", () => {
  it("puts RB rushing and receiving stats before valid passing columns", () => {
    const columns = getHistoricalStatColumnsForPosition("RB", allColumns);
    expect(columns.slice(0, 5)).toEqual(["Rush Yds", "Rush TD", "Receptions", "Rec Yds", "Rec TD"]);
    expect(columns.indexOf("Pass Yds")).toBeGreaterThan(columns.indexOf("Rec TD"));
  });

  it("uses the approved QB, WR, TE, and K priorities", () => {
    expect(getHistoricalStatColumnsForPosition("QB", allColumns).slice(0, 7)).toEqual([
      "Pass Yds", "Pass TD", "INT", "Comp", "Pass Att", "Rush Yds", "Rush TD",
    ]);
    expect(getHistoricalStatColumnsForPosition("WR", allColumns).slice(0, 5)).toEqual([
      "Receptions", "Rec Yds", "Rec TD", "Rush Yds", "Rush TD",
    ]);
    expect(getHistoricalStatColumnsForPosition("TE", allColumns).slice(0, 5)).toEqual([
      "Receptions", "Rec Yds", "Rec TD", "Rush Yds", "Rush TD",
    ]);
    expect(getHistoricalStatColumnsForPosition("K", allColumns).slice(0, 5)).toEqual([
      "FGM", "FGA", "FG%", "XPM", "XPA",
    ]);
    expect(getHistoricalStatColumnsForPosition("WR", allColumns)).not.toContain("Targets");
  });

  it("uses the historical row position before the current player position", () => {
    const seasons = [{ position: "RB", summary: [], categories: [] }];
    expect(historicalStatsTablePosition(seasons, "WR")).toBe("RB");
    expect(getHistoricalStatColumnsForPosition(historicalStatsTablePosition(seasons, "WR"), allColumns)[0]).toBe("Rush Yds");
  });

  it("uses a safe generic order for unsupported provider positions without duplicates", () => {
    const columns = getHistoricalStatColumnsForPosition("CB", ["Rec Yds", "Pass Yds", "Pass Yds", "Games"]);
    expect(columns).toEqual(["Games", "Pass Yds", "Rec Yds"]);
  });

  it("preserves recorded zeroes, renders null as unavailable upstream, and never restores fantasy points", () => {
    const values = historicalStatValuesForSeason({
      position: "RB",
      summary: [
        { label: "Fantasy Points", value: null },
        { label: "Pass Yds", value: 0 },
        { label: "Rush Yds", value: 1373 },
      ],
      categories: [
        { key: "rushing", label: "Rushing", stats: [{ label: "TD", value: 10 }] },
        { key: "receiving", label: "Receiving", stats: [{ label: "Receptions", value: 0 }, { label: "Yards", value: null }] },
      ],
    });

    expect(values.get("Pass Yds")).toBe(0);
    expect(values.get("Rush TD")).toBe(10);
    expect(values.get("Receptions")).toBe(0);
    expect(values.get("Rec Yds")).toBeNull();
    expect([...values.keys()]).not.toContain("Fantasy Points");
  });
});
