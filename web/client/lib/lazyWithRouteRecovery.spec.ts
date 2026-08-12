// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest";

import {
  isStaleRouteImportError,
  loadRouteModuleWithRecovery,
} from "./lazyWithRouteRecovery";

const createStorage = () => {
  const entries = new Map<string, string>();
  return {
    getItem: vi.fn((key: string) => entries.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => entries.set(key, value)),
    removeItem: vi.fn((key: string) => entries.delete(key)),
  };
};

describe("lazy route recovery", () => {
  it("recognizes only stale Vite dynamic-import failures", () => {
    expect(
      isStaleRouteImportError(
        new TypeError("Failed to fetch dynamically imported module"),
      ),
    ).toBe(true);
    expect(
      isStaleRouteImportError(new Error("Importing a module script failed.")),
    ).toBe(true);
    expect(isStaleRouteImportError(new Error("league request failed"))).toBe(
      false,
    );
  });

  it("clears an earlier reload marker after a route imports successfully", async () => {
    const storage = createStorage();
    storage.setItem("join", "attempted");

    await expect(
      loadRouteModuleWithRecovery(async () => ({ page: "join" }), {
        storage,
        reloadKey: "join",
      }),
    ).resolves.toEqual({ page: "join" });

    expect(storage.removeItem).toHaveBeenCalledWith("join");
  });

  it("reloads exactly once for a stale route chunk", async () => {
    const storage = createStorage();
    const reload = vi.fn();
    const staleChunk = new TypeError(
      "Failed to fetch dynamically imported module",
    );

    await expect(
      loadRouteModuleWithRecovery(async () => Promise.reject(staleChunk), {
        storage,
        reload,
        reloadKey: "join",
      }),
    ).rejects.toThrow(staleChunk);
    await expect(
      loadRouteModuleWithRecovery(async () => Promise.reject(staleChunk), {
        storage,
        reload,
        reloadKey: "join",
      }),
    ).rejects.toThrow(staleChunk);

    expect(reload).toHaveBeenCalledTimes(1);
    expect(storage.setItem).toHaveBeenCalledWith("join", "attempted");
  });

  it("does not reload for an application exception", async () => {
    const storage = createStorage();
    const reload = vi.fn();

    await expect(
      loadRouteModuleWithRecovery(
        async () => Promise.reject(new Error("league request failed")),
        {
          storage,
          reload,
          reloadKey: "join",
        },
      ),
    ).rejects.toThrow("league request failed");

    expect(reload).not.toHaveBeenCalled();
  });
});
