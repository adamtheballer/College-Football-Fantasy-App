import { describe, expect, it } from "vitest";

import { formatDraftProjection } from "./draft-projections";

describe("formatDraftProjection", () => {
  it("shows the authoritative season projection before Week 1 even without a weekly projection", () => {
    expect(formatDraftProjection({ seasonProjection: 314, weeklyProjection: 0, hasWeeklyProjection: false })).toBe("314.0");
  });

  it("falls back to a weekly projection only when the season projection is unavailable", () => {
    expect(formatDraftProjection({ weeklyProjection: 18.25, hasWeeklyProjection: true })).toBe("18.3");
  });

  it("uses the verified statline season total when a partial player payload omits the primary annual field", () => {
    expect(
      formatDraftProjection({
        fallbackSeasonProjection: 314,
        weeklyProjection: 0,
        hasWeeklyProjection: false,
      })
    ).toBe("314.0");
  });

  it("shows an em dash only when no usable projection exists", () => {
    expect(formatDraftProjection({ weeklyProjection: 0, hasWeeklyProjection: false })).toBe("—");
  });
});
