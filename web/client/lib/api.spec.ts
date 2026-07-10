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

  it("surfaces FastAPI validation details instead of a generic 422", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [
            {
              type: "value_error",
              loc: ["body", "basics", "max_teams"],
              msg: "Value error, max_teams must be an even number of at least 2",
            },
            {
              type: "value_error",
              loc: ["body", "draft", "draft_datetime_utc"],
              msg: "Input should be a valid datetime",
            },
          ],
        }),
        {
          status: 422,
          statusText: "Unprocessable Entity",
          headers: { "Content-Type": "application/json" },
        }
      )
    );

    await expect(apiGet("/leagues")).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      message:
        "basics.max_teams: Value error, max_teams must be an even number of at least 2; draft.draft_datetime_utc: Input should be a valid datetime",
    });
  });
});
