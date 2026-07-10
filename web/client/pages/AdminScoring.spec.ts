import { describe, expect, it } from "vitest";

import { canRunLeagueWeekAction, parseCorrectionStats } from "./AdminScoring";

describe("AdminScoring helpers", () => {
  it("parses correction stats JSON objects", () => {
    expect(parseCorrectionStats('{"PassingYards":250}')).toEqual({ PassingYards: 250 });
  });

  it("rejects non-object correction stats", () => {
    expect(() => parseCorrectionStats("[]")).toThrow("Stats must be a JSON object.");
  });

  it("requires a positive integer league id for league-week actions", () => {
    expect(canRunLeagueWeekAction("1")).toBe(true);
    expect(canRunLeagueWeekAction("0")).toBe(false);
    expect(canRunLeagueWeekAction("abc")).toBe(false);
  });
});
