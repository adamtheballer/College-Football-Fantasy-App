import { apiPost } from "@/lib/api";

const BROWSER_PUSH_STORAGE_KEY = "cfb_browser_push_registered";

const base64UrlToUint8Array = (value: string) => {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const output = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) {
    output[index] = raw.charCodeAt(index);
  }
  return output;
};

const rememberRegistered = () => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(BROWSER_PUSH_STORAGE_KEY, "1");
};

const wasRegistered = () => {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(BROWSER_PUSH_STORAGE_KEY) === "1";
};

export async function ensureBrowserPushRegistration(forcePrompt = false): Promise<boolean> {
  if (typeof window === "undefined" || typeof navigator === "undefined") return false;
  if (!("Notification" in window)) return false;
  if (!("serviceWorker" in navigator)) return false;

  if (!forcePrompt && wasRegistered() && Notification.permission === "granted") {
    return true;
  }

  let permission = Notification.permission;
  if (permission === "default") {
    permission = await Notification.requestPermission();
  }
  if (permission !== "granted") return false;

  const registration = await navigator.serviceWorker.register("/service-worker.js");
  const vapidPublicKey = String(import.meta.env.VITE_WEB_PUSH_PUBLIC_KEY || "").trim();

  let deviceToken = "";
  if ("PushManager" in window && vapidPublicKey) {
    const existing = await registration.pushManager.getSubscription();
    const subscription =
      existing ||
      (await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlToUint8Array(vapidPublicKey),
      }));
    deviceToken = JSON.stringify(subscription.toJSON());
  } else {
    deviceToken = `browser:${navigator.userAgent}`;
  }

  if (!deviceToken) return false;
  await apiPost("/notifications/tokens", {
    device_token: deviceToken,
    platform: "web",
  });
  rememberRegistered();
  return true;
}
