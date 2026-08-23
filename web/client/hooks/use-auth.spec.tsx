// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/push-notifications", () => ({
  clearBrowserPushIdentity: vi.fn(),
  syncBrowserPushIdentity: vi.fn(),
}));

import { AuthProvider, useAuth } from "./use-auth";
import { hasSessionRestoreHint } from "@/lib/api";

const originalFetch = globalThis.fetch;

afterEach(() => {
  cleanup();
  globalThis.fetch = originalFetch;
  localStorage.clear();
  document.cookie = "cfb_session_present=; Max-Age=0; path=/";
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function AuthProbe() {
  const { isBootstrapping, isLoggedIn, user } = useAuth();
  return <output>{`${isBootstrapping}:${isLoggedIn}:${user?.firstName ?? "anonymous"}`}</output>;
}

describe("AuthProvider session restoration", () => {
  it("restores a valid cookie session when local access-token storage is empty", async () => {
    const storage = new Map<string, string>([["cfb_session_restore_hint", "1"]]);
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem: vi.fn((key: string) => storage.delete(key)),
      clear: vi.fn(() => storage.clear()),
    });
    expect(hasSessionRestoreHint()).toBe(true);
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        access_token: "fresh-access-token",
        access_token_expires_at: "2030-01-01T01:00:00Z",
      }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 7,
        first_name: "An1ski",
        email: "manager@example.com",
        is_admin: false,
        avatar_url: null,
      }), { status: 200, headers: { "Content-Type": "application/json" } }));

    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider><AuthProbe /></AuthProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("false:true:An1ski")).toBeTruthy());
    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/auth/refresh"),
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
    expect(globalThis.fetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/auth/me"),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer fresh-access-token" }) }),
    );
  });

  it("does not delay a public page with an auth refresh when no session hint exists", async () => {
    globalThis.fetch = vi.fn();

    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider><AuthProbe /></AuthProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("false:false:anonymous")).toBeTruthy());
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
