import { describe, expect, it } from "vitest";

import { computeBasicTradeValue, evaluateBasicTrade } from "./tradeAnalyzer";

describe("basic trade analyzer", () => {
  it("handles unknown positional rank without producing invalid values", () => {
    const value = computeBasicTradeValue({
      id: 1,
      name: "Example Player",
      pos: "RB",
      school: "Example State",
      fpts: 120,
      posRank: null,
    });

    expect(Number.isFinite(value)).toBe(true);
    expect(value).toBeGreaterThan(0);
  });

  it("labels results as a basic estimate", () => {
    const result = evaluateBasicTrade(
      [
        {
          id: 1,
          name: "Receive Player",
          pos: "WR",
          school: "Example State",
          fpts: 120,
          posRank: null,
        },
      ],
      [
        {
          id: 2,
          name: "Give Player",
          pos: "WR",
          school: "Example Tech",
          fpts: 120,
          posRank: null,
        },
      ]
    );

    expect(result.verdict).toMatch(/^Basic /);
  });
});
