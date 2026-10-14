import { useLayoutEffect, useRef } from "react";
import { useRuntimeCapabilities } from "@/components/RuntimeCompatibilityGate";
import { AppReviewCoordinator as Coordinator } from "@/lib/app-review";
import { claimReview, isNativeIosReviewRuntime, nativeReviewAdapter, observeNativeReviewAvailability, readReviewState, rememberReviewClaim, reviewConsumed } from "@/lib/native-app-review";
import { hasPendingGuide } from "@/lib/onboarding";
import { hasReviewPresentationBlocker, observeReviewPresentation } from "@/lib/review-presentation";

export const isReviewSafeRoute = (pathname: string) =>
  ["/", "/leagues", "/rosters", "/injury-center", "/alerts"].includes(pathname) ||
  /^\/league\/\d+\/(roster|matchup|watchlist|waivers|standings)$/.test(pathname);

const visible = (element: Element) => {
  const style = getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0;
};

export function reviewScreenIsUsable(document: Document): boolean {
  const main = document.querySelector("main");
  if (!main || !main.textContent?.trim() || !visible(main)) return false;
  if (Array.from(document.querySelectorAll('[role="dialog"], [role="alertdialog"], [aria-modal="true"], [role="menu"], [data-review-blocking="true"]')).some(visible)) return false;
  if (main.matches('[aria-busy="true"]') || Array.from(main.querySelectorAll('[aria-busy="true"]')).some(visible)) return false;
  return !document.activeElement?.matches('input, textarea, select, [contenteditable="true"]');
}

/** Mounted once by Layout. No UI and no changes to the auth/session providers. */
export function AppReviewCoordinator({ accountId, sessionReady, onboarding, screenKey, pathname }: {
  accountId: number | null; sessionReady: boolean; onboarding: boolean; screenKey: string; pathname: string;
}) {
  const { ios_app_review_enabled } = useRuntimeCapabilities();
  const state = useRef({ accountId, sessionReady, onboarding, screenKey, pathname, enabled: ios_app_review_enabled === true });
  const coordinator = useRef<Coordinator>();
  const refresh = useRef<() => void>(() => {});

  useLayoutEffect(() => {
    if (!isNativeIosReviewRuntime()) return;
    const controller = new Coordinator({ adapter: nativeReviewAdapter, state: readReviewState, claim: claimReview,
      consumed: reviewConsumed, remember: rememberReviewClaim, now: Date.now });
    coordinator.current = controller;
    let active = true;
    let nativeActive = true; // Native synchronize also checks the actual scene.
    const update = () => {
      const current = state.current;
      controller.update({ accountId: current.accountId, enabled: current.enabled, native: true,
        foreground: nativeActive && document.visibilityState === "visible",
        safe: current.sessionReady && !current.onboarding && current.accountId !== null && !hasPendingGuide(current.accountId) &&
          isReviewSafeRoute(current.pathname) && !hasReviewPresentationBlocker() && reviewScreenIsUsable(document),
        screenKey: current.screenKey });
    };
    refresh.current = update;
    const interaction = () => { controller.interrupt(); update(); };
    const mutation = new MutationObserver(update);
    mutation.observe(document.body, { subtree: true, childList: true, attributes: true,
      attributeFilter: ["role", "aria-modal", "aria-busy", "class", "style", "hidden", "data-review-blocking"] });
    const removePresentation = observeReviewPresentation(update);
    document.addEventListener("visibilitychange", update);
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", update);
    const interactionEvents = ["pointerdown", "keydown", "scroll"] as const;
    interactionEvents.forEach((event) => document.addEventListener(event, interaction, { capture: true, passive: true }));
    let removeNative: (() => Promise<void>) | undefined;
    void observeNativeReviewAvailability((event) => {
      if (!active) return;
      nativeActive = event.active;
      update();
    }).then((handle) => {
      if (!active) void handle.remove(); else removeNative = () => handle.remove();
    }).catch(() => { nativeActive = false; update(); });
    update();
    return () => {
      active = false;
      controller.dispose();
      coordinator.current = undefined;
      refresh.current = () => {};
      mutation.disconnect();
      removePresentation();
      document.removeEventListener("visibilitychange", update);
      document.removeEventListener("focusin", update);
      document.removeEventListener("focusout", update);
      interactionEvents.forEach((event) => document.removeEventListener(event, interaction, true));
      void removeNative?.();
    };
  }, []);

  useLayoutEffect(() => {
    state.current = { accountId, sessionReady, onboarding, screenKey, pathname, enabled: ios_app_review_enabled === true };
    refresh.current();
  }, [accountId, sessionReady, onboarding, screenKey, pathname, ios_app_review_enabled]);
  return null;
}
