import { describe, expect, it } from "vitest";

import { formatDraftProjection } from "./draft-projections";

describe("formatDraftProjection", () => {
  it("shows the authoritative season projection before Week 1", () => {
    expect(formatDraftProjection({ seasonProjection: 314 })).toBe("314.0");
  });

  it("prefers a current rest-of-season forecast after weekly updates", () => {
    expect(formatDraftProjection({ restOfSeasonProjection: 188, seasonProjection: 314 })).toBe("188.0");
  });

  it("renders unavailable instead of substituting a weekly projection", () => {
    expect(formatDraftProjection({})).toBe("—");
  });

  it("uses the verified statline season total when a partial player payload omits the primary annual field", () => {
    expect(
      formatDraftProjection({
        fallbackSeasonProjection: 314,
      })
    ).toBe("314.0");
  });

  it("shows an em dash only when no usable projection exists", () => {
    expect(formatDraftProjection({})).toBe("—");
  });
});
