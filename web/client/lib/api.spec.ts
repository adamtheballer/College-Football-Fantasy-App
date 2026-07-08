import { afterEach, describe, expect, it, vi } from "vitest";

import { AUTH_CHANGED_EVENT, AUTH_EXPIRED_EVENT } from "./auth-events";
import { apiGet, apiPost } from "./api";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.unstubAllGlobals();
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

  it("adds csrf headers to non-GET requests when the csrf cookie exists", async () => {
    vi.stubGlobal("document", { cookie: "cfb_csrf_token=test-csrf-token" });
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await apiPost("/auth/logout", {});

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-CSRF-Token": "test-csrf-token",
        }),
      })
    );
  });

  it("dispatches auth-expired events when refresh cannot recover a 401", async () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal("window", { dispatchEvent });
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "expired" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "expired refresh" }), { status: 401 }));

    await expect(apiGet("/leagues")).rejects.toMatchObject({ status: 401 });

    expect(dispatchEvent).toHaveBeenCalledWith(expect.objectContaining({ type: AUTH_EXPIRED_EVENT }));
    expect(dispatchEvent).toHaveBeenCalledWith(expect.objectContaining({ type: AUTH_CHANGED_EVENT }));
  });

  it("does not expire auth when refresh is unavailable due to network failure", async () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal("window", { dispatchEvent });
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "expired" }), { status: 401 }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(apiGet("/leagues")).rejects.toMatchObject({ status: 401 });

    expect(dispatchEvent).not.toHaveBeenCalledWith(expect.objectContaining({ type: AUTH_EXPIRED_EVENT }));
  });
});
