import { Capacitor } from "@capacitor/core";

const RESET_HOST = "collegefantasyfootball.org";

export const routeUniversalLink = (urlText: string) => {
  try {
    const url = new URL(urlText);
    if (
      url.protocol !== "https:" ||
      ![RESET_HOST, `www.${RESET_HOST}`].includes(url.hostname) ||
      url.username ||
      url.password
    )
      return;
    const challenge =
      /^\/weekly-challenges(?:\/(?:leaderboard|[1-9]\d*|modes\/(?:fanwars|millionaire|creator|survivor)|experiences\/[1-9]\d*))?\/?$/.test(
        url.pathname,
      ) ||
      /^\/challenges\/creator\/[a-z0-9][a-z0-9-]{1,79}$/.test(url.pathname);
    if (url.pathname !== "/reset-password" && !challenge) return;
    // Keep the token only in the route transition. ResetPassword removes it
    // from the visible URL immediately after reading it into component memory.
    if (
      `${window.location.pathname}${window.location.search}` ===
      `${url.pathname}${url.search}`
    )
      return;
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
  const launch = await App.getLaunchUrl();
  if (launch?.url) routeUniversalLink(launch.url);
};
