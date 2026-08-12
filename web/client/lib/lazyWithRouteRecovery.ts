import { lazy, type ComponentType } from "react";

type StorageLike = Pick<Storage, "getItem" | "removeItem" | "setItem">;

type RouteRecoveryEnvironment = {
  storage?: StorageLike | null;
  reload?: (() => void) | null;
  reloadKey?: string;
};

const ROUTE_RELOAD_KEY_PREFIX = "cfb_stale_route_reload";

export const isStaleRouteImportError = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /failed to fetch dynamically imported module|importing a module script failed|error loading dynamically imported module/i.test(
    message,
  );
};

const browserRouteRecoveryEnvironment = (): RouteRecoveryEnvironment => {
  if (typeof window === "undefined") return {};

  let storage: StorageLike | null = null;
  try {
    storage = window.sessionStorage;
  } catch {
    // Storage is optional. A stale route will still surface as a normal error
    // in browsers that block session storage entirely.
  }

  return {
    storage,
    reload: () => window.location.reload(),
    reloadKey: `${ROUTE_RELOAD_KEY_PREFIX}:${window.location.pathname}`,
  };
};

/**
 * A Vite deployment changes the hash in lazy route filenames. A tab that is
 * already open can ask Vercel for an old filename during navigation, even
 * though the fresh page bundle is available. Reload exactly once to get the
 * current route manifest; never retry unrelated application exceptions.
 */
export const loadRouteModuleWithRecovery = async <T>(
  loader: () => Promise<T>,
  overrides: RouteRecoveryEnvironment = {},
): Promise<T> => {
  const defaults = browserRouteRecoveryEnvironment();
  const storage = overrides.storage ?? defaults.storage;
  const reload = overrides.reload ?? defaults.reload;
  const reloadKey = overrides.reloadKey ?? defaults.reloadKey;

  try {
    const module = await loader();
    if (storage && reloadKey) {
      storage.removeItem(reloadKey);
    }
    return module;
  } catch (error) {
    if (
      !isStaleRouteImportError(error) ||
      !storage ||
      !reload ||
      !reloadKey ||
      storage.getItem(reloadKey)
    ) {
      throw error;
    }

    storage.setItem(reloadKey, "attempted");
    reload();
    throw error;
  }
};

export const lazyWithRouteRecovery = <T extends ComponentType<any>>(
  loader: () => Promise<{ default: T }>,
) => lazy(() => loadRouteModuleWithRecovery(loader));
