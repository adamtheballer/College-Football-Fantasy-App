// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ post: vi.fn() }));
const platform = vi.hoisted(() => ({ native: false }));
const nativeClient = vi.hoisted(() => ({
  initialize: vi.fn().mockResolvedValue(undefined),
  login: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn().mockResolvedValue(undefined),
  Notifications: {
    addEventListener: vi.fn(),
    permissionNative: vi.fn().mockResolvedValue(2),
    hasPermission: vi.fn().mockResolvedValue(true),
    requestPermission: vi.fn().mockResolvedValue(true),
    canRequestPermission: vi.fn().mockResolvedValue(true),
  },
  User: {
    pushSubscription: {
      optIn: vi.fn().mockResolvedValue(undefined),
      optOut: vi.fn().mockResolvedValue(undefined),
      getIdAsync: vi.fn().mockResolvedValue("native-subscription"),
      addEventListener: vi.fn(),
    },
  },
}));

vi.mock("@/lib/api", () => ({ apiPost: api.post }));
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => platform.native }, registerPlugin: () => ({ state: async () => ({ authorization: 2, environment: "development", canPrompt: true }), bindAccount: vi.fn().mockResolvedValue(undefined), setBadge: vi.fn().mockResolvedValue(undefined) }) }));
vi.mock("@onesignal/capacitor-plugin", () => ({ default: nativeClient }));

afterEach(() => {
  vi.unstubAllEnvs();
  vi.clearAllMocks();
  vi.resetModules();
  platform.native = false;
});

describe("native OneSignal push registration", () => {
  it("uses the iOS bridge and stores its subscription under the authenticated user", async () => {
    vi.stubEnv("VITE_ONESIGNAL_APP_ID", "test-app-id");
    platform.native = true;
    api.post.mockResolvedValue({ id: 1, user_id: 7, provider: "onesignal", platform: "ios", enabled: true, delivery_configured: true });

    const { prepareBrowserPush, resolvePushState } = await import("./push-notifications");

    await expect(resolvePushState()).resolves.toBe("pending");
    await prepareBrowserPush(7);

    expect(nativeClient.initialize).toHaveBeenCalledWith("test-app-id");
    expect(nativeClient.login).toHaveBeenCalledWith("cfb_user:7");
    await expect(resolvePushState()).resolves.toBe("granted");
    expect(api.post).toHaveBeenCalledWith("/notifications/tokens", expect.objectContaining({
      subscription_id: "native-subscription",
      platform: "ios",
      provider: "onesignal", account_id: 7,
    }));
  });
});
