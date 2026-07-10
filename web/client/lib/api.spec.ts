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

  it("flattens FastAPI validation errors into actionable messages", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [
            {
              loc: ["body", "settings", "scoring_json"],
              msg: "Value error, unknown scoring rule 'pass_yds_per_pt'",
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

    await expect(apiPost("/leagues", {})).rejects.toMatchObject({
      status: 422,
      message: "settings.scoring_json: Value error, unknown scoring rule 'pass_yds_per_pt'",
    });
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

  it("refreshes an expired access token before retrying auth profile checks", async () => {
    vi.stubGlobal("document", { cookie: "cfb_csrf_token=test-csrf-token" });
    const storage = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    });
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "expired access token" }), { status: 401 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "fresh-access-token",
            access_token_expires_at: "2026-08-01T00:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 1, first_name: "Adam", email: "adam@example.com" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

    const profile = await apiGet("/auth/me");

    expect(profile).toMatchObject({ id: 1, first_name: "Adam" });
    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/auth/refresh"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-CSRF-Token": "test-csrf-token",
        }),
      })
    );
    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining("/auth/me"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer fresh-access-token",
        }),
      })
    );
  });
});
