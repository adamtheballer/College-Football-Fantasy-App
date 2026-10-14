import { apiPost } from "@/lib/api";
import { Capacitor, registerPlugin } from "@capacitor/core";
import { queuePushTap } from "@/lib/push-navigation";

type OneSignalClient = {
  init: (options: Record<string, unknown>) => Promise<void>;
  login: (externalId: string) => Promise<void>;
  logout: () => Promise<void>;
  Notifications: { requestPermission: () => Promise<void> };
  User: {
    PushSubscription: {
      id?: string | null;
      addEventListener?: (
        event: "change",
        listener: (event: { current?: { id?: string | null } }) => void,
      ) => void;
    };
  };
};

type NativeOneSignalClient = {
  initialize: (appId: string) => Promise<void>;
  login: (externalId: string) => Promise<void>;
  logout: () => Promise<void>;
  Notifications: {
    permissionNative: () => Promise<number>;
    addEventListener: {
      (event: "click", callback: (event: { notification: { additionalData?: Record<string, unknown> } }) => void): void;
      (event: "foregroundWillDisplay", callback: (event: { getNotification: () => { additionalData?: Record<string, unknown> }; preventDefault: (discard?: boolean) => void }) => void): void;
    };
    hasPermission: () => Promise<boolean>;
    addForegroundListener?: (listener: (event: unknown) => void) => void;
    requestPermission: (fallbackToSettings?: boolean) => Promise<boolean>;
    canRequestPermission: () => Promise<boolean>;
  };
  User: {
    pushSubscription: {
      getIdAsync: () => Promise<string | null>;
      optOut: () => Promise<void>;
      optIn: () => Promise<void>;
      addEventListener?: (
        event: "change",
        listener: (event: { current?: { id?: string } }) => void,
      ) => void;
    };
  };
};

declare global {
  interface Window {
    OneSignalDeferred?: Array<(oneSignal: OneSignalClient) => void | Promise<void>>;
  }
}

export type BrowserPushState = "default" | "granted" | "denied" | "unsupported" | "unconfigured" | "provisional" | "pending" | "failed";

const appId = import.meta.env.VITE_ONESIGNAL_APP_ID?.trim();
let loader: Promise<void> | null = null;
let initialized = false;
let readyClient: OneSignalClient | null = null;
let activePushUserId: number | null = null;
let observedPushClient: OneSignalClient | null = null;
let nativeLoader: Promise<NativeOneSignalClient> | null = null;
let nativeInitialized = false;
let nativeInitialization: Promise<void> | null = null;
let observedNativePushClient: NativeOneSignalClient | null = null;
let registeredSubscriptionKey: string | null = null;
let registrationInFlight: Promise<void> | null = null;
let registrationInFlightKey: string | null = null;
let generation = 0;
let registrationFailed = false;
let identityWork: Promise<unknown> = Promise.resolve();
const nativeRuntime = registerPlugin<{
  state: () => Promise<{ authorization: number; environment: "development" | "distribution"; canPrompt: boolean }>;
  openSettings: () => Promise<void>;
  bindAccount: (options: { accountId: number | null }) => Promise<void>;
  setBadge: (options: { count: number }) => Promise<void>;
}>("PushRuntime");
export const updatePhoneNotificationBadge = async (count: number) => { if (isNativeApp()) await nativeRuntime.setBadge({ count }); };
export const openPhoneNotificationSettings = () => nativeRuntime.openSettings();
const notifyState = () => window.dispatchEvent(new Event("cffb-push-state-changed"));
const activateAccount = (userId: number) => {
  if (activePushUserId === userId) return;
  generation++;
  activePushUserId = userId;
  registeredSubscriptionKey = null;
  registrationFailed = false;
  if (isNativeApp()) void nativeRuntime.bindAccount({ accountId: null }).catch(() => undefined);
};
const serializeIdentity = <T>(work: () => Promise<T>): Promise<T> => {
  const result = identityWork.catch(() => undefined).then(work);
  identityWork = result.catch(() => undefined);
  return result;
};
const installation = () => {
  const key = "cffb_push_installation";
  const stored = localStorage.getItem(key);
  if (stored) {
    try { const parsed = JSON.parse(stored); if (typeof parsed.id === "string" && typeof parsed.secret === "string") return parsed as { id: string; secret: string }; } catch { /* Replace malformed local metadata. */ }
  }
  const value = { id: crypto.randomUUID(), secret: Array.from(crypto.getRandomValues(new Uint8Array(32)), (byte) => byte.toString(16).padStart(2, "0")).join("") };
  localStorage.setItem(key, JSON.stringify(value));
  return value;
};

const isIosHomeScreenWebApp = (): boolean => {
  const userAgent = navigator.userAgent ?? "";
  const isIos = /iPad|iPhone|iPod/.test(userAgent);
  if (!isIos) return true;

  const navigatorWithStandalone = navigator as Navigator & { standalone?: boolean };
  return navigatorWithStandalone.standalone === true || window.matchMedia?.("(display-mode: standalone)").matches === true;
};

const isNativeApp = (): boolean => Capacitor.isNativePlatform();

const loadNativeOneSignal = async (): Promise<NativeOneSignalClient> => {
  if (!nativeLoader) {
    nativeLoader = import("@onesignal/capacitor-plugin").then((module) => module.default as NativeOneSignalClient);
  }
  return nativeLoader;
};

const withNativeOneSignal = async <T>(callback: (client: NativeOneSignalClient) => Promise<T>): Promise<T> => {
  if (!appId) throw new Error("Push notifications are not configured for this app.");
  const client = await loadNativeOneSignal();
  if (!nativeInitialization) nativeInitialization = (async () => {
    // Subscribe before initialization so a cold-launch click is retained through auth restoration.
    client.Notifications.addEventListener("click", (event) => queuePushTap(event.notification.additionalData));
    client.Notifications.addEventListener("foregroundWillDisplay", (event) => {
      const data = event.getNotification().additionalData;
      // Use the same recipient/expiry boundary as the native service
      // extension. APNs acceptance may precede eventual foreground delivery.
      if (!activePushUserId || data?.recipient_user_id !== activePushUserId ||
          typeof data.expires_at !== "number" || !Number.isFinite(data.expires_at) ||
          data.expires_at <= Date.now() / 1000) event.preventDefault(true);
    });
    await client.initialize(appId);
    nativeInitialized = true;
  })().catch((error) => { nativeInitialization = null; throw error; });
  await nativeInitialization;
  return callback(client);
};

export const getBrowserPushState = (): BrowserPushState => {
  if (!appId) return "unconfigured";
  // Native permission is asynchronous. The settings panel resolves it after
  // mount; default here keeps its first render deterministic and web-safe.
  if (isNativeApp()) return "default";
  if (typeof window === "undefined" || !("Notification" in window) || !("serviceWorker" in navigator)) {
    return "unsupported";
  }
  if (!window.isSecureContext) return "unsupported";
  // iOS allows Web Push only from a Home Screen web app. Safari tabs can
  // expose the generic browser APIs but cannot complete a usable push setup.
  if (!isIosHomeScreenWebApp()) return "unsupported";
  return Notification.permission;
};

export const resolvePushState = async (): Promise<BrowserPushState> => {
  if (!isNativeApp()) return getBrowserPushState();
  if (!appId) return "unconfigured";
  try {
    const state = await nativeRuntime.state();
    if (state.authorization === 0) return "default";
    if (state.authorization === 1) return "denied";
    if (registrationFailed) return "failed";
    if (!registeredSubscriptionKey) return "pending";
    return state.authorization === 3 || state.authorization === 4 ? "provisional" : "granted";
  } catch { return "unsupported"; }
};

/** Initialize click handling at launch, without asking for permission. */
export const initializeNativePush = async () => {
  if (isNativeApp() && appId) await withNativeOneSignal(async () => undefined);
};

const loadSdk = () => {
  if (loader) return loader;
  loader = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-cfb-onesignal="true"]');
    if (existing) {
      if (window.OneSignalDeferred) resolve();
      else existing.addEventListener("load", () => resolve(), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js";
    script.async = true;
    script.dataset.cfbOnesignal = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Unable to load the push notification service."));
    document.head.appendChild(script);
  });
  return loader;
};

const withOneSignal = async <T>(callback: (client: OneSignalClient) => Promise<T>): Promise<T> => {
  // OneSignal reads this queue as its SDK initializes, so it must exist before
  // the remote script is appended—not after its load event.
  window.OneSignalDeferred = window.OneSignalDeferred || [];
  await loadSdk();
  return new Promise<T>((resolve, reject) => {
    window.OneSignalDeferred.push(async (client) => {
      try {
        if (!initialized) {
          await client.init({
            appId,
            serviceWorkerPath: "/OneSignalSDKWorker.js",
            serviceWorkerParam: { scope: "/" },
          });
          initialized = true;
        }
        readyClient = client;
        resolve(await callback(client));
      } catch (error) {
        reject(error instanceof Error ? error : new Error("Unable to configure push notifications."));
      }
    });
  });
};

const stableExternalId = (userId: number) => `cfb_user:${userId}`;

const registerPushSubscription = async (
  userId: number, subscriptionId: string | null | undefined, platform: "web" | "ios" = "web",
): Promise<void> => {
  if (activePushUserId !== userId) throw new Error("Account changed during notification setup.");
  if (!subscriptionId) { notifyState(); return; }
  const epoch = generation;
  const key = `${userId}:${subscriptionId}`;
  if (registeredSubscriptionKey === key) return;
  if (registrationInFlight && registrationInFlightKey === key) return registrationInFlight;
  registrationInFlightKey = key;
  const device = platform === "ios" ? installation() : null;
  const runtime = platform === "ios" ? await nativeRuntime.state() : null;
  if (epoch !== generation || activePushUserId !== userId) return;
  registrationInFlight = apiPost<{ id?: number; user_id?: number | null; provider?: string; platform?: string; enabled?: boolean; delivery_configured?: boolean }>("/notifications/tokens", {
    subscription_id: subscriptionId, platform, provider: "onesignal", account_id: userId,
    ...(device ? { installation_id: device.id, installation_secret: device.secret, app_id: appId, environment: runtime?.environment } : {}),
  }).then(async (result) => {
    if (epoch !== generation || activePushUserId !== userId) return;
    if (platform === "ios" && (result?.delivery_configured !== true ||
        !Number.isSafeInteger(result.id) || (result.id ?? 0) <= 0 || result.user_id !== userId ||
        result.provider !== "onesignal" || result.platform !== "ios" || result.enabled !== true)) {
      throw new Error("The server did not confirm this account's enabled phone delivery.");
    }
    if (result?.delivery_configured === false) throw new Error("Phone delivery is not configured on the server yet.");
    if (platform === "ios") await nativeRuntime.bindAccount({ accountId: userId });
    if (epoch !== generation || activePushUserId !== userId) return;
    registeredSubscriptionKey = key;
    registrationFailed = false;
    notifyState();
  }).catch((error) => {
    if (epoch === generation) { registrationFailed = true; notifyState(); }
    throw error;
  }).finally(() => {
    if (registrationInFlightKey === key) { registrationInFlight = null; registrationInFlightKey = null; }
  });
  return registrationInFlight;
};

const observeNativePushSubscription = (client: NativeOneSignalClient, userId: number) => {
  activateAccount(userId);
  if (observedNativePushClient === client || !client.User.pushSubscription.addEventListener) return;

  observedNativePushClient = client;
  client.User.pushSubscription.addEventListener("change", (event) => {
    const currentUserId = activePushUserId;
    if (currentUserId === null) return;
    void serializeIdentity(async () => {
      if (activePushUserId !== currentUserId) return;
      await registerPushSubscription(currentUserId, await client.User.pushSubscription.getIdAsync(), "ios");
    }).catch(() => {
      // A later foreground launch retries registration from the authoritative SDK state.
    });
  });
};

const observePushSubscription = (client: OneSignalClient, userId: number) => {
  activateAccount(userId);
  if (observedPushClient === client || !client.User.PushSubscription.addEventListener) return;

  observedPushClient = client;
  client.User.PushSubscription.addEventListener("change", (event) => {
    // OneSignal may assign the Subscription ID after the system permission
    // prompt resolves. Register from the authoritative change event instead
    // of treating a transient null ID as a completed setup.
    const currentUserId = activePushUserId;
    if (currentUserId === null) return;
    void registerPushSubscription(currentUserId, event.current?.id ?? client.User.PushSubscription.id).catch(() => {
      // The next SDK change or signed-in session sync retries registration.
    });
  });
};

/**
 * Prepare the SDK after the user explicitly opens notification settings, but
 * never prompt here. iOS requires the eventual permission API call to occur
 * directly inside the button gesture, not after SDK loading or login awaits.
 */
export const prepareBrowserPush = async (userId: number): Promise<void> => {
  if (isNativeApp()) {
    if (!appId) return;
    activateAccount(userId);
    const epoch = generation;
    await serializeIdentity(() => withNativeOneSignal(async (client) => {
      if (epoch !== generation || activePushUserId !== userId) return;
      await client.login(stableExternalId(userId));
      if (epoch !== generation || activePushUserId !== userId) return;
      observeNativePushSubscription(client, userId);
      if (await client.Notifications.hasPermission()) {
        await client.User.pushSubscription.optIn();
        await registerPushSubscription(userId, await client.User.pushSubscription.getIdAsync(), "ios");
      }
    }));
    return;
  }
  const initialState = getBrowserPushState();
  if (initialState === "denied" || initialState === "unsupported" || initialState === "unconfigured") return;
  activateAccount(userId);
  await withOneSignal(async (client) => {
    if (activePushUserId !== userId) return;
    await client.login(stableExternalId(userId));
    observePushSubscription(client, userId);
  });
};

export const enableBrowserPush = async (userId: number): Promise<BrowserPushState> => {
  if (isNativeApp()) {
    if (!appId) return "unconfigured";
    activateAccount(userId);
    const epoch = generation;
    try {
      await prepareBrowserPush(userId);
      await withNativeOneSignal(async (client) => {
        const state = await nativeRuntime.state();
        if (epoch !== generation || activePushUserId !== userId) return;
        if (state.authorization === 0 && state.canPrompt) {
          await withReviewPresentationBlocker(() => client.Notifications.requestPermission(false));
        }
        if (epoch !== generation || activePushUserId !== userId) return;
        if (await client.Notifications.hasPermission()) {
          await client.User.pushSubscription.optIn();
          await registerPushSubscription(userId, await client.User.pushSubscription.getIdAsync(), "ios");
        }
      });
      return await resolvePushState();
    } catch (error) {
      if (epoch === generation) { registrationFailed = true; notifyState(); }
      throw error;
    }
  }
  const initialState = getBrowserPushState();
  if (initialState === "denied" || initialState === "unsupported" || initialState === "unconfigured") return initialState;
  const client = readyClient;
  if (!client) throw new Error("Notification setup is still preparing. Please try again in a moment.");
  activateAccount(userId);
  // Do not put an await before this invocation. iOS otherwise loses the tap
  // activation and leaves Notification.permission at "default" with no prompt.
  const permissionRequest = Notification.permission === "default"
    ? client.Notifications.requestPermission()
    : Promise.resolve();
  await permissionRequest;
  if (Notification.permission === "granted") {
    await registerPushSubscription(userId, client.User.PushSubscription.id);
  }
  return Notification.permission;
};

/** Associate an already-permitted subscription after login without prompting. */
export const syncBrowserPushIdentity = async (userId: number): Promise<void> => {
  if (isNativeApp()) {
    try { await prepareBrowserPush(userId); } catch { registrationFailed = true; notifyState(); }
    return;
  }
  if (getBrowserPushState() !== "granted") return;
  try {
    activateAccount(userId);
    await withOneSignal(async (client) => {
      if (activePushUserId !== userId) return;
      await client.login(stableExternalId(userId));
      if (activePushUserId !== userId) return;
      observePushSubscription(client, userId);
      await registerPushSubscription(userId, client.User.PushSubscription.id);
    });
  } catch { /* Settings exposes setup errors; foreground/session sync retries. */ }
};

/** Detach this browser from the authenticated OneSignal identity on logout. */
export const clearBrowserPushIdentity = async (): Promise<void> => {
  const userId = activePushUserId;
  generation++;
  activePushUserId = null;
  registeredSubscriptionKey = null;
  registrationFailed = false;
  registrationInFlight = null;
  registrationInFlightKey = null;
  const device = isNativeApp() ? installation() : null;
  // Start the authenticated detach synchronously before AuthProvider clears credentials.
  if (isNativeApp()) void nativeRuntime.bindAccount({ accountId: null }).catch(() => undefined);
  const detach = userId === null ? Promise.resolve() : apiPost("/notifications/tokens/detach", {
    account_id: userId,
    ...(device ? { installation_id: device.id, installation_secret: device.secret } : { subscription_id: readyClient?.User.PushSubscription.id }),
  }).catch(() => undefined);
  await serializeIdentity(async () => {
    try {
      if (isNativeApp() && appId) {
        await withNativeOneSignal(async (client) => { await client.User.pushSubscription.optOut(); await client.logout(); });
      } else if (readyClient) { await readyClient.logout(); }
    } catch { /* Backend binding remains fail-closed; retry binding at next verified login. */ }
  });
  await detach;
  notifyState();
};
import { withReviewPresentationBlocker } from "@/lib/review-presentation";
