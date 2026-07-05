import { afterEach, describe, expect, it, vi } from "vitest";

import { apiGet } from "./api";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("api client", () => {
  it("wraps browser network failures in an actionable ApiError", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(apiGet("/health")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      message: expect.stringContaining("Unable to reach the backend API"),
    });
  });
});
