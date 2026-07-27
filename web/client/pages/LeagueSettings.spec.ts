import { describe, expect, it } from "vitest";

import { formatDateTime, formatTradeAssets } from "./LeagueSettings";

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
