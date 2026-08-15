import { apiPost } from "@/lib/api";

type OneSignalClient = {
  init: (options: Record<string, unknown>) => Promise<void>;
  login: (externalId: string) => Promise<void>;
  logout: () => Promise<void>;
  Notifications: { requestPermission: () => Promise<void> };
  User: { PushSubscription: { id?: string | null } };
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

export const getBrowserPushState = (): BrowserPushState => {
  if (!appId) return "unconfigured";
  if (typeof window === "undefined" || !("Notification" in window) || !("serviceWorker" in navigator)) {
    return "unsupported";
  }
  if (!window.isSecureContext) return "unsupported";
  return Notification.permission;
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
        resolve(await callback(client));
      } catch (error) {
        reject(error instanceof Error ? error : new Error("Unable to configure push notifications."));
      }
    });
  });
};

const stableExternalId = (userId: number) => `cfb_user:${userId}`;

export const enableBrowserPush = async (userId: number): Promise<BrowserPushState> => {
  const initialState = getBrowserPushState();
  if (initialState === "denied" || initialState === "unsupported" || initialState === "unconfigured") return initialState;
  return withOneSignal(async (client) => {
    await client.login(stableExternalId(userId));
    if (Notification.permission === "default") {
      await client.Notifications.requestPermission();
    }
    if (Notification.permission === "granted" && client.User.PushSubscription.id) {
      await apiPost("/notifications/tokens", {
        subscription_id: client.User.PushSubscription.id,
        platform: "web",
        provider: "onesignal",
      });
    }
    return Notification.permission;
  });
};

/** Associate an already-permitted subscription after login without prompting. */
export const syncBrowserPushIdentity = async (userId: number): Promise<void> => {
  if (getBrowserPushState() !== "granted") return;
  try {
    await withOneSignal(async (client) => {
      await client.login(stableExternalId(userId));
      if (client.User.PushSubscription.id) {
        await apiPost("/notifications/tokens", {
          subscription_id: client.User.PushSubscription.id,
          platform: "web",
          provider: "onesignal",
        });
      }
    });
  } catch {
    // Identity synchronization is best effort after login. The explicit
    // Settings action surfaces setup errors directly to the user.
  }
};

/** Detach this browser from the authenticated OneSignal identity on logout. */
export const clearBrowserPushIdentity = (): void => {
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
