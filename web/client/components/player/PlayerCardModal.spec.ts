import { describe, expect, it } from "vitest";

import { statValue } from "@/lib/playerProjectionStats";

import { formatPlayerCardValue, getPlayerCardPalette, resolvePlayerCardProjectionStats } from "./PlayerCardModal";

describe("PlayerCardModal helpers", () => {
  it("formats empty player-card fields with an em dash fallback", () => {
    expect(formatPlayerCardValue(null)).toBe("—");
    expect(formatPlayerCardValue(undefined)).toBe("—");
    expect(formatPlayerCardValue("")).toBe("—");
  });

  it("formats finite numeric player-card fields for display", () => {
    expect(formatPlayerCardValue(1305)).toBe("1,305");
    expect(formatPlayerCardValue(Number.NaN)).toBe("—");
  });

  it("uses a position-specific palette when available and a default otherwise", () => {
    expect(getPlayerCardPalette("RB").pill).toContain("emerald");
    expect(getPlayerCardPalette("UNKNOWN").pill).toContain("cyan");
  });

  it("uses sheet projection stats from the loaded card when the selected row has none", () => {
    const projectedStats = resolvePlayerCardProjectionStats(
      {
        id: 5278,
        name: "Ian Strong",
        school: "California",
        position: "WR",
        projectedPoints: 294.9,
      },
      {
        player: {
          id: 5278,
          name: "Ian Strong",
          position: "WR",
          school: "California",
          sheet_projected_season_points: 199.5,
          sheet_projection_stats: {
            receptions: 63,
            rec_yds: 925,
            rec_tds: 7,
          },
        } as never,
        about: { source: "local" },
        injuries: [],
        season_stats: [],
        historical_stats: null,
      }
    );

    expect(statValue(projectedStats, ["receptions"])).toBe(63);
    expect(statValue(projectedStats, ["rec_yds"])).toBe(925);
    expect(statValue(projectedStats, ["rec_tds"])).toBe(7);
    expect(statValue(projectedStats, ["fpts"])).toBe(294.9);
  });

  it("keeps weekly matchup projection ranges on roster player cards", () => {
    const projectedStats = resolvePlayerCardProjectionStats({
      id: 12,
      name: "Lanorris Sellers",
      school: "South Carolina",
      position: "QB",
      projectedPoints: 23.4,
      projection: {
        fpts: 23.4,
        floor: 14.2,
        ceiling: 34.8,
        boomProb: 0.31,
        bustProb: 0.16,
      },
    });

    expect(statValue(projectedStats, ["fpts"])).toBe(23.4);
    expect(statValue(projectedStats, ["floor"])).toBe(14.2);
    expect(statValue(projectedStats, ["ceiling"])).toBe(34.8);
    expect(statValue(projectedStats, ["boomProb"])).toBe(0.31);
    expect(statValue(projectedStats, ["bustProb"])).toBe(0.16);
  });
});
