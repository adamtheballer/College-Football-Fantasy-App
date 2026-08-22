import { apiPost } from "@/lib/api";
import { Capacitor } from "@capacitor/core";

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
    hasPermission: () => Promise<boolean>;
    requestPermission: (fallbackToSettings?: boolean) => Promise<boolean>;
    canRequestPermission: () => Promise<boolean>;
  };
  User: {
    pushSubscription: {
      getIdAsync: () => Promise<string | null>;
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

export type BrowserPushState = "default" | "granted" | "denied" | "unsupported" | "unconfigured";

const appId = import.meta.env.VITE_ONESIGNAL_APP_ID?.trim();
let loader: Promise<void> | null = null;
let initialized = false;
let readyClient: OneSignalClient | null = null;
let activePushUserId: number | null = null;
let observedPushClient: OneSignalClient | null = null;
let nativeLoader: Promise<NativeOneSignalClient> | null = null;
let nativeInitialized = false;
let observedNativePushClient: NativeOneSignalClient | null = null;
let registeredSubscriptionKey: string | null = null;
let registrationInFlight: Promise<void> | null = null;
let registrationInFlightKey: string | null = null;

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
  if (!nativeInitialized) {
    await client.initialize(appId);
    nativeInitialized = true;
  }
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
    return (await withNativeOneSignal((client) => client.Notifications.hasPermission())) ? "granted" : "default";
  } catch {
    return "unsupported";
  }
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
  userId: number,
  subscriptionId: string | null | undefined,
  platform: "web" | "ios" = "web",
): Promise<void> => {
  if (!subscriptionId) return;
  const key = `${userId}:${subscriptionId}`;
  if (registeredSubscriptionKey === key) return;
  if (registrationInFlight && registrationInFlightKey === key) return registrationInFlight;

  registrationInFlightKey = key;
  registrationInFlight = apiPost("/notifications/tokens", {
    subscription_id: subscriptionId,
    platform,
    provider: "onesignal",
  })
    .then(() => {
      registeredSubscriptionKey = key;
    })
    .finally(() => {
      if (registrationInFlightKey === key) {
        registrationInFlight = null;
        registrationInFlightKey = null;
      }
    });
  return registrationInFlight;
};

const observeNativePushSubscription = (client: NativeOneSignalClient, userId: number) => {
  activePushUserId = userId;
  if (observedNativePushClient === client || !client.User.pushSubscription.addEventListener) return;

  observedNativePushClient = client;
  client.User.pushSubscription.addEventListener("change", (event) => {
    const currentUserId = activePushUserId;
    if (currentUserId === null) return;
    void registerPushSubscription(currentUserId, event.current?.id, "ios").catch(() => {
      // A later foreground launch retries registration from the authoritative SDK state.
    });
  });
};

const observePushSubscription = (client: OneSignalClient, userId: number) => {
  activePushUserId = userId;
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
    await withNativeOneSignal(async (client) => {
      await client.login(stableExternalId(userId));
      observeNativePushSubscription(client, userId);
      if (await client.Notifications.hasPermission()) {
        await registerPushSubscription(userId, await client.User.pushSubscription.getIdAsync(), "ios");
      }
    });
    return;
  }
  const initialState = getBrowserPushState();
  if (initialState === "denied" || initialState === "unsupported" || initialState === "unconfigured") return;
  await withOneSignal(async (client) => {
    await client.login(stableExternalId(userId));
    observePushSubscription(client, userId);
  });
};

export const enableBrowserPush = async (userId: number): Promise<BrowserPushState> => {
  if (isNativeApp()) {
    if (!appId) return "unconfigured";
    try {
      return await withNativeOneSignal(async (client) => {
        activePushUserId = userId;
        await client.login(stableExternalId(userId));
        observeNativePushSubscription(client, userId);
        const granted = await client.Notifications.hasPermission() || await client.Notifications.requestPermission(false);
        if (granted) {
          await registerPushSubscription(userId, await client.User.pushSubscription.getIdAsync(), "ios");
          return "granted";
        }
        return (await client.Notifications.canRequestPermission()) ? "default" : "denied";
      });
    } catch {
      return "unsupported";
    }
  }
  const initialState = getBrowserPushState();
  if (initialState === "denied" || initialState === "unsupported" || initialState === "unconfigured") return initialState;
  const client = readyClient;
  if (!client) throw new Error("Notification setup is still preparing. Please try again in a moment.");
  activePushUserId = userId;
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
  if (getBrowserPushState() !== "granted") return;
  try {
    await withOneSignal(async (client) => {
      await client.login(stableExternalId(userId));
      observePushSubscription(client, userId);
      await registerPushSubscription(userId, client.User.PushSubscription.id);
    });
  } catch {
    // Identity synchronization is best effort after login. The explicit
    // Settings action surfaces setup errors directly to the user.
  }
};

/** Detach this browser from the authenticated OneSignal identity on logout. */
export const clearBrowserPushIdentity = (): void => {
  activePushUserId = null;
  readyClient = null;
  void (async () => {
    // Detach the authenticated application subscription before releasing the
    // OneSignal identity.  A later account may then register this browser;
    // without this scoped server-side step ownership remains protected.
    try {
      await apiPost("/notifications/tokens/detach", {});
    } catch {
      // Local logout and provider cleanup must remain best effort when the
      // API is unavailable; the active row remains protected until detach.
    }
    if (isNativeApp()) {
      if (!appId) return;
      try {
        await withNativeOneSignal(async (client) => {
          await client.logout();
        });
      } catch {
        // Native identity cleanup remains best effort during local logout.
      }
      return;
    }
    if (getBrowserPushState() !== "granted") return;
    try {
      await withOneSignal(async (client) => {
        await client.logout();
      });
    } catch {
      // Local application logout must not be blocked by SDK loading failures.
    }
  })();
};
