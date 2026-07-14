import { describe, expect, it } from "vitest";

import { CFB27_RATINGS } from "@/lib/cfb27Ratings";
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
  it("keeps critical CFB27-rated players in the source board", () => {
    const jeremiah = CFB27_RATINGS.find(
      (rating) => rating.name === "Jeremiah Smith" && rating.school === "Ohio State" && rating.pos === "WR"
    );
    const ahmad = CFB27_RATINGS.find(
      (rating) => rating.name === "Ahmad Hardy" && rating.school === "Missouri" && rating.pos === "RB"
    );

    expect(jeremiah?.ovr).toBe(99);
    expect(ahmad?.ovr).toBe(96);
  });

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

  it("includes Ahmad Hardy from the matched CFB27 board", () => {
    const rows = buildPlayerCompareRows([
      player({
        id: 10,
        name: "Ahmad Hardy",
        school: "Missouri",
        pos: "RB",
        boardRank: 1,
        rank: 1,
      }),
      player({
        id: 11,
        name: "Kewan Lacy",
        school: "Ole Miss",
        pos: "RB",
        boardRank: 3,
        rank: 3,
      }),
    ]);

    const ahmad = rows.find((row) => row.name === "Ahmad Hardy");
    const kewan = rows.find((row) => row.name === "Kewan Lacy");
    expect(ahmad?.cfb27Overall).toBe(96);
    expect(ahmad?.valueOverall).toBe(96);
    expect(kewan?.cfb27Overall).toBe(96);
  });

  it("collapses duplicate backend rows to the canonical ranked player", () => {
    const rows = buildPlayerCompareRows([
      player({
        id: 20,
        name: "Ahmad Hardy",
        school: "Missouri",
        pos: "RB",
        boardRank: null,
        rank: 0,
        adp: 0,
      }),
      player({
        id: 21,
        name: "AHMAD HARDY",
        school: "MISSOURI",
        pos: "RB",
        boardRank: 1,
        rank: 1,
        adp: 1,
      }),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe(21);
    expect(rows[0].cfb27Overall).toBe(96);
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
