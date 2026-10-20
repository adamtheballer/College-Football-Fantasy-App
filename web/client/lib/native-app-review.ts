import { Capacitor, registerPlugin, type PluginListenerHandle } from "@capacitor/core";
import { apiReviewRequest } from "@/lib/api";
import type { ReviewAdapter, ReviewClaim, ReviewState } from "@/lib/app-review";

interface AppReviewPlugin extends ReviewAdapter {
  addListener(event: "availabilityChanged", listener: (event: { active: boolean }) => void): Promise<PluginListenerHandle>;
}
const native = registerPlugin<AppReviewPlugin>("AppReview");
export const isNativeIosReviewRuntime = () => Capacitor.isNativePlatform() && Capacitor.getPlatform() === "ios" && window.location.protocol === "capacitor:";
export const nativeReviewAdapter: ReviewAdapter = native;
export const observeNativeReviewAvailability = (listener: (event: { active: boolean }) => void) => native.addListener("availabilityChanged", listener);
export const readReviewState = (accountId: number, signal: AbortSignal) => apiReviewRequest<ReviewState>("/app-review/state", accountId, signal);
export const claimReview = (accountId: number, app_version: string, app_build: string, signal: AbortSignal) => apiReviewRequest<ReviewClaim>("/app-review/claim", accountId, signal, { app_version, app_build });
const consumedAccounts = new Set<number>();
const key = (id: number) => `cffb_ios_review_claimed_${id}`;
export function reviewConsumed(id: number): boolean {
  if (consumedAccounts.has(id)) return true;
  try { return localStorage.getItem(key(id)) === "true"; } catch { return false; }
}
export function rememberReviewClaim(id: number): void {
  consumedAccounts.add(id);
  try { localStorage.setItem(key(id), "true"); } catch { /* Memory + server remain authoritative. */ }
}

export const acknowledgeReviewInvocation = (accountId: number) => apiReviewRequest<ReviewState>("/app-review/invoked", accountId, new AbortController().signal, {});
