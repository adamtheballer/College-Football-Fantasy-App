import { describe, expect, it } from "vitest";

import { buildProjectedStats, statRowsForPosition, statValue } from "@/lib/playerProjectionStats";

describe("playerProjectionStats", () => {
  it("reads Google Sheet projection headers regardless of casing and spacing", () => {
    const stats = {
      "Rush Yards": "123",
      "Rush TDs": 4,
      Rec: "48",
      "Receiving Yards": 548,
      "Receiving TDs": "6",
    };

    const rows = statRowsForPosition("TE");

    expect(statValue(stats, rows.find((row) => row.label === "Rush Yds")!.projectionKeys)).toBe(123);
    expect(statValue(stats, rows.find((row) => row.label === "Rush TD")!.projectionKeys)).toBe(4);
    expect(statValue(stats, rows.find((row) => row.label === "Rec")!.projectionKeys)).toBe(48);
    expect(statValue(stats, rows.find((row) => row.label === "Rec Yds")!.projectionKeys)).toBe(548);
    expect(statValue(stats, rows.find((row) => row.label === "Rec TD")!.projectionKeys)).toBe(6);
  });

  it("lets imported sheet stats override zero fallback projection fields", () => {
    const projectedStats = buildProjectedStats(
      {
        receptions: 0,
        receivingYards: 0,
        receivingTds: 0,
        rushingYards: 0,
        rushingTds: 0,
      },
      124.5,
      {
        receptions: 49,
        receivingYards: 548,
        receivingTds: 6,
      }
    );

    const rows = statRowsForPosition("TE");

    expect(statValue(projectedStats, rows.find((row) => row.label === "Rec")!.projectionKeys)).toBe(49);
    expect(statValue(projectedStats, rows.find((row) => row.label === "Rec Yds")!.projectionKeys)).toBe(548);
    expect(statValue(projectedStats, rows.find((row) => row.label === "Rec TD")!.projectionKeys)).toBe(6);
  });

  it("supports QB and kicker sheet aliases", () => {
    const qbRows = statRowsForPosition("QB");
    const kickerRows = statRowsForPosition("K");

    expect(statValue({ "Pass Yards": 3100, "Pass TDs": 28, INT: 7 }, qbRows[0].projectionKeys)).toBe(3100);
    expect(statValue({ "Pass Yards": 3100, "Pass TDs": 28, INT: 7 }, qbRows[1].projectionKeys)).toBe(28);
    expect(statValue({ "Pass Yards": 3100, "Pass TDs": 28, INT: 7 }, qbRows[2].projectionKeys)).toBe(7);
    expect(statValue({ "Field Goals": 21, "Extra Points": 45 }, kickerRows[0].projectionKeys)).toBe(21);
    expect(statValue({ "Field Goals": 21, "Extra Points": 45 }, kickerRows[1].projectionKeys)).toBe(45);
  });
});
