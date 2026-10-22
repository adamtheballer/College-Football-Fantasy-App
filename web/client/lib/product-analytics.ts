import { Capacitor } from "@capacitor/core";
import { App } from "@capacitor/app";
import { apiChallengeWrite } from "@/lib/api";
export type ProductEventKind =
  | "session"
  | "challenge_view"
  | "challenge_start"
  | "challenge_submit"
  | "challenge_share"
  | "guide_complete"
  | "notification_open";
const sent = new Set<string>();
/** Optional, daily deduplicated, no free-text payloads or third-party SDK. */
export async function trackProductEvent(
  accountId: number,
  kind: ProductEventKind,
  challengeId?: number,
) {
  try {
    if (
      navigator.doNotTrack === "1" ||
      localStorage.getItem(`cffb_analytics_opt_out_${accountId}`) === "true"
    )
      return;
    const key = `${accountId}:${kind}:${challengeId ?? 0}:${new Date().toISOString().slice(0, 10)}`;
    if (sent.has(key)) return;
    sent.add(key);
    const native = Capacitor.isNativePlatform();
    const info = native ? await App.getInfo().catch(() => null) : null;
    await apiChallengeWrite(accountId, "POST", "/product/events", {
      kind,
      challenge_id: challengeId ?? null,
      platform: native ? Capacitor.getPlatform() : "web",
      app_version: info?.version ?? null,
      app_build: info?.build ?? null,
    });
  } catch {
    /* Observation must never block an entry or account action. */
  }
}
