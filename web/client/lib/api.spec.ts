import { afterEach, describe, expect, it, vi } from "vitest";

import { AUTH_CHANGED_EVENT, apiGet, clearAccessTokenSession } from "./api";

describe("api client errors", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("surfaces a clear backend URL error when fetch cannot reach the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => {
        throw new TypeError("Failed to fetch");
      })
    );
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    await expect(apiGet("/health")).rejects.toThrow(
      "Unable to reach the backend API. Check that FastAPI is running and VITE_API_BASE_URL points to the correct public or local backend URL."
    );
  });

  it("broadcasts auth changes when the access token session is cleared", () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal("window", { dispatchEvent });

    clearAccessTokenSession();

    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    expect(dispatchEvent.mock.calls[0][0]).toBeInstanceOf(Event);
    expect(dispatchEvent.mock.calls[0][0].type).toBe(AUTH_CHANGED_EVENT);
  });
});
