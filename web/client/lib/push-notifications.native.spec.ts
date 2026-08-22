// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ post: vi.fn() }));
const platform = vi.hoisted(() => ({ native: false }));
const nativeClient = vi.hoisted(() => ({
  initialize: vi.fn().mockResolvedValue(undefined),
  login: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn().mockResolvedValue(undefined),
  Notifications: {
    hasPermission: vi.fn().mockResolvedValue(true),
    requestPermission: vi.fn().mockResolvedValue(true),
    canRequestPermission: vi.fn().mockResolvedValue(true),
  },
  User: {
    pushSubscription: {
      getIdAsync: vi.fn().mockResolvedValue("native-subscription"),
      addEventListener: vi.fn(),
    },
  },
}));

vi.mock("@/lib/api", () => ({ apiPost: api.post }));
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => platform.native } }));
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
    api.post.mockResolvedValue({ id: 1, enabled: true });

    const { prepareBrowserPush, resolvePushState } = await import("./push-notifications");

    await expect(resolvePushState()).resolves.toBe("granted");
    await prepareBrowserPush(7);

    expect(nativeClient.initialize).toHaveBeenCalledWith("test-app-id");
    expect(nativeClient.login).toHaveBeenCalledWith("cfb_user:7");
    expect(api.post).toHaveBeenCalledWith("/notifications/tokens", {
      subscription_id: "native-subscription",
      platform: "ios",
      provider: "onesignal",
    });
  });
});
