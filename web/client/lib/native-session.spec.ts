// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

const secureStorage = vi.hoisted(() => ({
  get: vi.fn(),
  set: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("capacitor-secure-storage-plugin", () => ({ SecureStoragePlugin: secureStorage }));

import {
  clearNativeRefreshToken,
  readNativeRefreshToken,
  saveNativeRefreshToken,
} from "./native-session";
import { restoreAccessTokenSession } from "./api";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  secureStorage.get.mockReset();
  secureStorage.set.mockReset();
  secureStorage.remove.mockReset();
});

const useNativeRuntime = () => {
  vi.stubGlobal("window", {
    location: { protocol: "capacitor:", origin: "capacitor://localhost" },
    dispatchEvent: vi.fn(),
  });
  vi.stubGlobal("localStorage", {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  });
};

describe("native refresh session", () => {
  it("rotates a Keychain token without a WebView cookie", async () => {
    useNativeRuntime();
    secureStorage.get.mockResolvedValue({ value: "old-refresh-token" });
    secureStorage.set.mockResolvedValue({ value: true });
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        access_token: "new-access-token",
        access_token_expires_at: "2030-01-01T01:00:00Z",
        refresh_token: "new-refresh-token",
      }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    await expect(restoreAccessTokenSession()).resolves.toBe("refreshed");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/auth/refresh"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CFFB-Native-Session": "ios" }),
        body: JSON.stringify({ refresh_token: "old-refresh-token" }),
      }),
    );
    expect(secureStorage.set).toHaveBeenCalledWith({
      key: "cffb_native_refresh_token", value: "new-refresh-token",
    });
  });

  it("removes a revoked native token but retains it on a transient failure", async () => {
    useNativeRuntime();
    secureStorage.get.mockResolvedValue({ value: "refresh-token" });
    secureStorage.remove.mockResolvedValue({ value: true });
    globalThis.fetch = vi.fn().mockResolvedValueOnce(new Response("", { status: 503 }));
    await expect(restoreAccessTokenSession()).resolves.toBe("transient_failure");
    expect(secureStorage.remove).not.toHaveBeenCalled();

    globalThis.fetch = vi.fn().mockResolvedValueOnce(new Response("", { status: 401 }));
    await expect(restoreAccessTokenSession()).resolves.toBe("terminal_failure");
    expect(secureStorage.remove).toHaveBeenCalledWith({ key: "cffb_native_refresh_token" });
  });

  it("fails closed when Keychain cannot save the rotated token", async () => {
    useNativeRuntime();
    secureStorage.get.mockResolvedValue({ value: "old-refresh-token" });
    secureStorage.set.mockRejectedValue(new Error("Keychain unavailable"));
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        access_token: "new-access-token",
        access_token_expires_at: "2030-01-01T01:00:00Z",
        refresh_token: "new-refresh-token",
      }), { status: 200 }),
    );
    await expect(restoreAccessTokenSession()).resolves.toBe("transient_failure");
  });

  it("does not save an absent refresh token and ignores missing-key cleanup", async () => {
    useNativeRuntime();
    await expect(saveNativeRefreshToken(null)).rejects.toThrow("did not provide");
    secureStorage.get.mockRejectedValue(new Error("Item with given key does not exist"));
    await expect(readNativeRefreshToken()).resolves.toBeNull();
    await expect(clearNativeRefreshToken()).resolves.toBeUndefined();
    expect(secureStorage.remove).not.toHaveBeenCalled();
  });
});
