import { describe, expect, it } from "vitest";

import { buildPlayerCompareRows } from "@/lib/playerCompareValue";
import type { Player } from "@/types/player";

const player = (overrides: Partial<Player>): Player => ({
  id: 1,
  name: "Test Player",
  school: "Test",
  pos: "RB",
  conf: "N/A",
  rank: 1,
  boardRank: 1,
  adp: 1,
  posRank: 1,
  rostered: 0,
  status: "HEALTHY",
  projection: { fpts: 100 },
  history: [],
  analysis: "",
  ...overrides,
});

describe("buildPlayerCompareRows", () => {
  it("uses matched CFB27 ratings as the Week 1 OVR baseline", () => {
    const rows = buildPlayerCompareRows([
      player({
        id: 1,
        name: "Arch Manning",
        school: "Texas",
        pos: "QB",
        boardRank: 6,
        rank: 6,
        projection: { fpts: 500 },
      }),
      player({
        id: 2,
        name: "Jeremiah Smith",
        school: "Ohio State",
        pos: "WR",
        boardRank: 40,
        rank: 40,
        projection: { fpts: 100 },
      }),
    ]);

    expect(rows[0].name).toBe("Jeremiah Smith");
    expect(rows[0].cfb27Overall).toBe(99);
    expect(rows[0].valueOverall).toBe(99);
    expect(rows[0].compareRank).toBe(1);
    expect(rows[1].name).toBe("Arch Manning");
    expect(rows[1].cfb27Overall).toBe(91);
    expect(rows[1].valueOverall).toBe(91);
  });

  it("does not invent a Week 1 overall from projections when CFB27 data is missing", () => {
    const rows = buildPlayerCompareRows([
      player({
        id: 1,
        name: "Projection Only Player",
        school: "Unknown",
        pos: "RB",
        projection: { fpts: 999 },
        sheetProjectedSeasonPoints: 999,
      }),
    ]);

    expect(rows[0].cfb27Overall).toBeNull();
    expect(rows[0].valueOverall).toBeNull();
  });

  it("shifts later-season value toward actual performance and position peers", () => {
    const rows = buildPlayerCompareRows(
      [
        player({
          id: 1,
          name: "Low Production Player",
          school: "Unknown",
          pos: "RB",
          projection: { fpts: 100 },
          history: [{ year: 2026, stats: { fpts: 40 } }],
        }),
        player({
          id: 2,
          name: "High Production Player",
          school: "Unknown",
          pos: "RB",
          projection: { fpts: 100 },
          history: [{ year: 2026, stats: { fpts: 140 } }],
        }),
      ],
      { week: 6 }
    );

    expect(rows[0].name).toBe("High Production Player");
    expect(rows[0].valueOverall).toBeGreaterThan(rows[1].valueOverall ?? 0);
    expect(rows[0].cfb27Overall).toBeNull();
  });
});
