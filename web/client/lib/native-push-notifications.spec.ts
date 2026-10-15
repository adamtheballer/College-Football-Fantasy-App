// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const mock = vi.hoisted(() => ({ authorization: 2, subscription: "phone-id" as string | null, canPrompt: true, post: vi.fn(), login: vi.fn(), logout: vi.fn(), request: vi.fn(), optIn: vi.fn(), optOut: vi.fn(), callbacks: new Map<string, (event: any) => void>(), change: null as null | ((event: any) => void) }));
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => true, getPlatform: () => "ios" }, registerPlugin: () => ({ state: async () => ({ authorization: mock.authorization, environment: "development", canPrompt: mock.canPrompt }), openSettings: vi.fn(), bindAccount: vi.fn().mockResolvedValue(undefined), setBadge: vi.fn().mockResolvedValue(undefined) }) }));
vi.mock("@/lib/api", () => ({ apiPost: mock.post }));
vi.mock("@onesignal/capacitor-plugin", () => ({ default: {
  initialize: vi.fn(), login: mock.login, logout: mock.logout,
  Notifications: { hasPermission: async () => mock.authorization >= 2, permissionNative: async () => mock.authorization, canRequestPermission: async () => mock.authorization === 0, requestPermission: mock.request, addEventListener: (event: string, callback: (event: any) => void) => mock.callbacks.set(event, callback) },
  User: { pushSubscription: { getIdAsync: async () => mock.subscription, optIn: mock.optIn, optOut: mock.optOut, addEventListener: (_event: string, callback: (event: any) => void) => { mock.change = callback; } } },
} }));
beforeEach(() => {
  vi.stubEnv("VITE_ONESIGNAL_APP_ID", "native-app"); mock.authorization = 2; mock.subscription = "phone-id"; mock.canPrompt = true;
  mock.post.mockImplementation(async (_path,body) => ({ id: 1, user_id: body.account_id, provider: "onesignal", platform: "ios", enabled: true, delivery_configured: true })); mock.login.mockResolvedValue(undefined); mock.logout.mockResolvedValue(undefined); mock.optIn.mockResolvedValue(undefined); mock.optOut.mockResolvedValue(undefined); mock.callbacks.clear(); mock.change = null;
  localStorage.clear(); sessionStorage.clear();
});
afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); vi.resetModules(); vi.unstubAllEnvs(); });
describe("native account-bound push lifecycle", () => {
  it("registers on session restoration without prompting and sends installation metadata", async () => {
    const push = await import("./push-notifications"); await push.syncBrowserPushIdentity(7);
    expect(mock.request).not.toHaveBeenCalled(); expect(mock.login).toHaveBeenCalledWith("cfb_user:7");
    expect(mock.post).toHaveBeenCalledWith("/notifications/tokens", expect.objectContaining({ account_id: 7, subscription_id: "phone-id", app_id: "native-app", environment: "development", installation_id: expect.any(String), installation_secret: expect.any(String) }));
    expect(await push.resolvePushState()).toBe("granted");
  });
  it("keeps registration pending for a null SDK id and recovers from the subscription observer", async () => {
    mock.subscription = null; const push = await import("./push-notifications");
    expect(await push.enableBrowserPush(7)).toBe("pending"); expect(mock.post).not.toHaveBeenCalled();
    mock.subscription = "new-token"; mock.change?.({ current: { id: "new-token" } });
    await vi.waitFor(() => expect(mock.post).toHaveBeenCalledTimes(1));
    await vi.waitFor(async () => expect(await push.resolvePushState()).toBe("granted"));
  });
  it("never calls a denied permission prompt repeatedly", async () => {
    mock.authorization = 1; const push = await import("./push-notifications");
    expect(await push.enableBrowserPush(7)).toBe("denied"); expect(await push.enableBrowserPush(7)).toBe("denied");
    expect(mock.request).not.toHaveBeenCalled(); expect(mock.post).not.toHaveBeenCalled();
  });
  it("does not display enabled after backend failure and retries on a later foreground sync", async () => {
    mock.post.mockRejectedValue(new Error("registration unavailable")); const push = await import("./push-notifications");
    await expect(push.enableBrowserPush(7)).rejects.toThrow("registration unavailable");
    expect(await push.resolvePushState()).toBe("failed");
    mock.post.mockResolvedValue({id:1,user_id:7,provider:"onesignal",platform:"ios",enabled:true,delivery_configured:true}); await push.syncBrowserPushIdentity(7);
    expect(await push.resolvePushState()).toBe("granted");
  });
  it("exposes provisional authorization after successful device registration", async () => {
    mock.authorization = 3; const push = await import("./push-notifications");
    expect(await push.enableBrowserPush(7)).toBe("provisional"); expect(mock.request).not.toHaveBeenCalled();
  });
  it("blocks App Review during an in-context Apple permission request", async () => {
    mock.authorization = 0; const push = await import("./push-notifications");
    const presentation = await import("./review-presentation");
    mock.request.mockImplementation(async () => { expect(presentation.hasReviewPresentationBlocker()).toBe(true); mock.authorization = 2; return true; });
    expect(await push.enableBrowserPush(7)).toBe("granted"); expect(presentation.hasReviewPresentationBlocker()).toBe(false);
  });
  it("detaches only the installation and re-registers after a same-account login", async () => {
    const push = await import("./push-notifications"); await push.syncBrowserPushIdentity(7); await push.clearBrowserPushIdentity();
    expect(mock.post).toHaveBeenCalledWith("/notifications/tokens/detach", expect.objectContaining({ account_id: 7, installation_id: expect.any(String) }));
    expect(mock.optOut).toHaveBeenCalledTimes(1); expect(mock.logout).toHaveBeenCalledTimes(1);
    await push.syncBrowserPushIdentity(7); expect(mock.post.mock.calls.filter(([path]) => path === "/notifications/tokens")).toHaveLength(2);
  });
  it("ignores a late old-account SDK login when another account takes over", async () => {
    let resolve!: () => void; mock.login.mockImplementationOnce(() => new Promise<void>((done) => { resolve = done; }));
    const push = await import("./push-notifications"); const first = push.prepareBrowserPush(1);
    await vi.waitFor(() => expect(mock.login).toHaveBeenCalledWith("cfb_user:1"));
    const second = push.prepareBrowserPush(2); resolve(); await first; await second;
    expect(mock.post).toHaveBeenCalledTimes(1); expect(mock.post.mock.calls[0][1].account_id).toBe(2);
  });
  it("buffers cold-launch taps and preserves a single native foreground banner only for the recipient", async () => {
    const push = await import("./push-notifications"); await push.initializeNativePush();
    mock.callbacks.get("click")?.({ notification: { additionalData: { event_id: 12, recipient_user_id: 7, url: "https://evil.test" } } });
    expect((await import("./push-navigation")).readPendingPushTap()?.eventId).toBe(12);
    await push.syncBrowserPushIdentity(7); const preventDefault = vi.fn();
    mock.callbacks.get("foregroundWillDisplay")?.({ getNotification: () => ({ additionalData: { recipient_user_id: 7, expires_at: Date.now() / 1000 + 60 } }), preventDefault });
    expect(preventDefault).not.toHaveBeenCalled();
    mock.callbacks.get("foregroundWillDisplay")?.({ getNotification: () => ({ additionalData: { recipient_user_id: 8 } }), preventDefault });
    expect(preventDefault).toHaveBeenCalledWith(true);
  });
  it.each([undefined, null, true, "9999999999", Number.NaN, Number.POSITIVE_INFINITY, 0])("suppresses malformed or expired foreground metadata %s", async (expiry) => {
    const push = await import("./push-notifications"); await push.initializeNativePush();
    await push.syncBrowserPushIdentity(7);
    const preventDefault = vi.fn();
    mock.callbacks.get("foregroundWillDisplay")?.({ getNotification: () => ({ additionalData: { recipient_user_id: 7, expires_at: expiry } }), preventDefault });
    expect(preventDefault).toHaveBeenCalledWith(true);
  });
  it("suppresses a foreground alert exactly when its server-issued lifetime expires", async () => {
    const push = await import("./push-notifications"); await push.initializeNativePush();
    await push.syncBrowserPushIdentity(7);
    const now = Date.now(); vi.spyOn(Date, "now").mockReturnValue(now);
    const preventDefault = vi.fn();
    mock.callbacks.get("foregroundWillDisplay")?.({ getNotification: () => ({ additionalData: { recipient_user_id: 7, expires_at: now / 1000 } }), preventDefault });
    expect(preventDefault).toHaveBeenCalledWith(true);
  });
});

it.each([{}, {delivery_configured:false}, {id:0}, {user_id:999}, {enabled:false}, {platform:"web"}, {provider:"other"}])(
 "does not report enabled on an unconfirmed or foreign registration (%j)", async override=>{
  mock.post.mockResolvedValue({id:1,user_id:7,provider:"onesignal",platform:"ios",enabled:true,delivery_configured:true,...override,
    ...(Object.keys(override).length===0?{delivery_configured:undefined}:{})});
  const push=await import("./push-notifications");
  await push.syncBrowserPushIdentity(7);
  expect(await push.resolvePushState()).toBe("failed");
 });
