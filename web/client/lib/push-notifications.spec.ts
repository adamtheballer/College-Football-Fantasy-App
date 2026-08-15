// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiPost: api.post }));

type PushChangeListener = (event: { current?: { id?: string | null } }) => void;

const prepareBrowser = (permissionRef: { value: "default" | "granted" | "denied" }) => {
  vi.stubEnv("VITE_ONESIGNAL_APP_ID", "test-app-id");
  Object.defineProperty(globalThis.navigator, "userAgent", { configurable: true, value: "Mozilla/5.0 (test browser)" });
  Object.defineProperty(globalThis.navigator, "standalone", { configurable: true, value: undefined });
  Object.defineProperty(globalThis, "Notification", {
    configurable: true,
    value: { get permission() { return permissionRef.value; } },
  });
  Object.defineProperty(globalThis.navigator, "serviceWorker", {
    configurable: true,
    value: {},
  });
  Object.defineProperty(globalThis.window, "isSecureContext", {
    configurable: true,
    value: true,
  });
  window.OneSignalDeferred = [];
  const script = document.createElement("script");
  script.dataset.cfbOnesignal = "true";
  document.head.appendChild(script);
};

const initializeWith = async (client: {
  init: ReturnType<typeof vi.fn>;
  login: ReturnType<typeof vi.fn>;
  logout: ReturnType<typeof vi.fn>;
  Notifications: { requestPermission: ReturnType<typeof vi.fn> };
  User: { PushSubscription: { id: string | null; addEventListener: ReturnType<typeof vi.fn> } };
}) => {
  await vi.waitFor(() => expect(window.OneSignalDeferred).toHaveLength(1));
  await window.OneSignalDeferred?.[0](client);
};

afterEach(() => {
  vi.unstubAllEnvs();
  vi.clearAllMocks();
  vi.resetModules();
  document.querySelectorAll("script[data-cfb-onesignal='true']").forEach((node) => node.remove());
  delete window.OneSignalDeferred;
});

describe("OneSignal subscription registration", () => {
  it("requires an iPhone Home Screen web app before offering web push", async () => {
    const permission: { value: "default" | "granted" | "denied" } = { value: "default" };
    prepareBrowser(permission);
    Object.defineProperty(globalThis.navigator, "userAgent", { configurable: true, value: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)" });
    Object.defineProperty(globalThis.navigator, "standalone", { configurable: true, value: false });
    Object.defineProperty(globalThis.window, "matchMedia", { configurable: true, value: vi.fn(() => ({ matches: false })) });
    const { getBrowserPushState } = await import("./push-notifications");

    expect(getBrowserPushState()).toBe("unsupported");
  });

  it("registers the subscription that OneSignal creates after the permission prompt", async () => {
    const permission: { value: "default" | "granted" | "denied" } = { value: "default" };
    prepareBrowser(permission);
    const listeners: PushChangeListener[] = [];
    const client = {
      init: vi.fn().mockResolvedValue(undefined),
      login: vi.fn().mockResolvedValue(undefined),
      logout: vi.fn().mockResolvedValue(undefined),
      Notifications: {
        requestPermission: vi.fn().mockImplementation(async () => {
          permission.value = "granted";
        }),
      },
      User: {
        PushSubscription: {
          id: null,
          addEventListener: vi.fn((_event: "change", listener: PushChangeListener) => listeners.push(listener)),
        },
      },
    };
    api.post.mockResolvedValue({ id: 12, enabled: true });
    const { enableBrowserPush, prepareBrowserPush } = await import("./push-notifications");

    const preparation = prepareBrowserPush(7);
    await initializeWith(client);
    await preparation;
    const setup = enableBrowserPush(7);
    await expect(setup).resolves.toBe("granted");
    expect(api.post).not.toHaveBeenCalled();
    expect(listeners).toHaveLength(1);

    listeners[0]({ current: { id: "subscription-created-after-grant" } });

    await vi.waitFor(() => expect(api.post).toHaveBeenCalledWith(
      "/notifications/tokens",
      {
        subscription_id: "subscription-created-after-grant",
        platform: "web",
        provider: "onesignal",
      },
    ));
  });

  it("registers an already-existing permitted subscription during login sync", async () => {
    const permission: { value: "default" | "granted" | "denied" } = { value: "granted" };
    prepareBrowser(permission);
    const client = {
      init: vi.fn().mockResolvedValue(undefined),
      login: vi.fn().mockResolvedValue(undefined),
      logout: vi.fn().mockResolvedValue(undefined),
      Notifications: { requestPermission: vi.fn().mockResolvedValue(undefined) },
      User: {
        PushSubscription: {
          id: "restored-subscription",
          addEventListener: vi.fn(),
        },
      },
    };
    api.post.mockResolvedValue({ id: 13, enabled: true });
    const { syncBrowserPushIdentity } = await import("./push-notifications");

    const sync = syncBrowserPushIdentity(7);
    await initializeWith(client);
    await sync;

    expect(api.post).toHaveBeenCalledWith(
      "/notifications/tokens",
      {
        subscription_id: "restored-subscription",
        platform: "web",
        provider: "onesignal",
      },
    );
  });
});
