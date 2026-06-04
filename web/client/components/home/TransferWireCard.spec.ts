import { describe, expect, it, vi } from "vitest";

import {
  formatNewsCategory,
  formatNewsRelativeTime,
  getNewsImpactLabel,
  TRANSFER_WIRE_EMPTY_MESSAGE,
  TRANSFER_WIRE_ERROR_MESSAGE,
} from "./TransferWireCard";

vi.mock("@/hooks/use-news", () => ({
  useNewsFeed: () => ({
    data: { data: [], total: 0, limit: 8, offset: 0 },
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
  }),
}));

describe("TransferWireCard display helpers", () => {
  it("formats category badges", () => {
    expect(formatNewsCategory("depth_chart")).toBe("DEPTH CHART");
    expect(formatNewsCategory("transfer")).toBe("TRANSFER");
  });

  it("labels relevance scores", () => {
    expect(getNewsImpactLabel(90)).toBe("High Impact");
    expect(getNewsImpactLabel(60)).toBe("Watch List");
    expect(getNewsImpactLabel(20)).toBe("Monitor");
  });

  it("formats relative source time", () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(formatNewsRelativeTime(fiveMinutesAgo)).toBe("5m ago");
    expect(formatNewsRelativeTime(null)).toBe("Recently discovered");
  });

  it("exposes empty and error state copy", () => {
    expect(TRANSFER_WIRE_EMPTY_MESSAGE).toContain("No fantasy-relevant news yet");
    expect(TRANSFER_WIRE_ERROR_MESSAGE).toBe("Unable to load Transfer Wire.");
  });
});
