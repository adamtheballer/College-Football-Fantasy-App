import { afterEach, describe, expect, it, vi } from "vitest";

import { apiGet, clearAccessTokenSession, storeAccessTokenSession } from "./api";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("api client", () => {
  it("notifies the auth provider when the access token session is cleared", () => {
    const dispatchEvent = vi.fn();
    const removeItem = vi.fn();
    vi.stubGlobal("window", { dispatchEvent });
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem,
    });

    clearAccessTokenSession();

    expect(removeItem).toHaveBeenCalledWith("cfb_access_token");
    expect(removeItem).toHaveBeenCalledWith("cfb_access_token_expires_at");
    expect(dispatchEvent).toHaveBeenCalledWith(expect.objectContaining({ type: "cfb-auth-changed" }));
  });

  it("wraps browser network failures in an actionable ApiError", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(apiGet("/health")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      message: expect.stringContaining("Local API is unavailable"),
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

  it("refreshes an expired access token for auth bootstrap instead of dropping the session", async () => {
    const storage = new Map<string, string>();
    vi.stubGlobal("window", { dispatchEvent: vi.fn(), location: { hostname: "localhost", protocol: "http:" } });
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem: vi.fn((key: string) => storage.delete(key)),
    });
    storeAccessTokenSession("expired-token", "2026-07-14T18:00:00Z");

    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired access token" }), {
          status: 401,
          statusText: "Unauthorized",
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "fresh-token",
            access_token_expires_at: "2026-07-14T19:00:00Z",
          }),
          {
            status: 200,
            statusText: "OK",
            headers: { "Content-Type": "application/json" },
          }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 2,
            first_name: "Emily",
            email: "emmab1167@icloud.com",
            email_verified_at: "2026-07-14T12:00:00Z",
          }),
          {
            status: 200,
            statusText: "OK",
            headers: { "Content-Type": "application/json" },
          }
        )
      );

    await expect(apiGet("/auth/me")).resolves.toMatchObject({
      id: 2,
      email: "emmab1167@icloud.com",
    });

    expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/auth/me"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer expired-token" }),
      })
    );
    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/auth/refresh"),
      expect.objectContaining({ credentials: "include", method: "POST" })
    );
    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining("/auth/me"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer fresh-token" }),
      })
    );
  });

  it("keeps the stored session when refresh fails from a transient network error", async () => {
    const storage = new Map<string, string>();
    const dispatchEvent = vi.fn();
    const removeItem = vi.fn((key: string) => storage.delete(key));
    vi.stubGlobal("window", { dispatchEvent, location: { hostname: "localhost", protocol: "http:" } });
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem,
    });
    storeAccessTokenSession("expired-token", "2026-07-14T18:00:00Z");

    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired access token" }), {
          status: 401,
          statusText: "Unauthorized",
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(apiGet("/auth/me")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      message: expect.stringContaining("you have not been signed out"),
    });

    expect(storage.get("cfb_access_token")).toBe("expired-token");
    expect(storage.get("cfb_access_token_expires_at")).toBe("2026-07-14T18:00:00Z");
    expect(removeItem).not.toHaveBeenCalledWith("cfb_access_token");
    expect(dispatchEvent).not.toHaveBeenCalledWith(expect.objectContaining({ type: "cfb-auth-changed" }));
  });

  it("clears the stored session when refresh is rejected as invalid", async () => {
    const storage = new Map<string, string>();
    const dispatchEvent = vi.fn();
    const removeItem = vi.fn((key: string) => storage.delete(key));
    vi.stubGlobal("window", { dispatchEvent, location: { hostname: "localhost", protocol: "http:" } });
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem,
    });
    storeAccessTokenSession("expired-token", "2026-07-14T18:00:00Z");

    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired access token" }), {
          status: 401,
          statusText: "Unauthorized",
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "invalid refresh token" }), {
          status: 401,
          statusText: "Unauthorized",
          headers: { "Content-Type": "application/json" },
        })
      );

    await expect(apiGet("/auth/me")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
    });

    expect(storage.get("cfb_access_token")).toBeUndefined();
    expect(storage.get("cfb_access_token_expires_at")).toBeUndefined();
    expect(removeItem).toHaveBeenCalledWith("cfb_access_token");
    expect(dispatchEvent).toHaveBeenCalledWith(expect.objectContaining({ type: "cfb-auth-changed" }));
  });
});
