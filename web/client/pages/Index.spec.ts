import { describe, expect, it } from "vitest";

import { formatDashboardPoints, formatDashboardStatus, formatDraftTime } from "./Index";

describe("home dashboard helpers", () => {
  it("formats backend statuses for user-facing copy", () => {
    expect(formatDashboardStatus("draft_scheduled")).toBe("draft scheduled");
    expect(formatDashboardStatus(null)).toBe("unknown");
  });

  it("formats draft times without exposing invalid dates", () => {
    expect(formatDraftTime(null)).toBe("Draft not scheduled");
    expect(formatDraftTime("not-a-date")).toBe("Draft not scheduled");
  });

  it("formats dashboard points with a safe empty fallback", () => {
    expect(formatDashboardPoints(118.44)).toBe("118.4");
    expect(formatDashboardPoints(null)).toBe("—");
    expect(formatDashboardPoints(Number.NaN)).toBe("—");
  });
});
