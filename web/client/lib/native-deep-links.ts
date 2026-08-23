import { Capacitor } from "@capacitor/core";

const RESET_HOST = "collegefantasyfootball.org";

const routeUniversalLink = (urlText: string) => {
  try {
    const url = new URL(urlText);
    if (url.protocol !== "https:" || url.hostname !== RESET_HOST || url.pathname !== "/reset-password") return;
    // Keep the token only in the route transition. ResetPassword removes it
    // from the visible URL immediately after reading it into component memory.
    window.history.pushState(null, "", `${url.pathname}${url.search}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  } catch {
    // Malformed links are deliberately ignored without logging their content.
  }
};

export const registerNativeDeepLinks = async () => {
  if (!Capacitor.isNativePlatform()) return;
  const { App } = await import("@capacitor/app");
  await App.addListener("appUrlOpen", ({ url }) => routeUniversalLink(url));
};
