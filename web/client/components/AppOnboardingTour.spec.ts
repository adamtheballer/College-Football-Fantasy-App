import { describe, expect, it } from "vitest";

import { getTourTooltipTop, TOUR_STEPS } from "./AppOnboardingTour";
import { shouldStartGuide } from "@/lib/onboarding";

describe("first-sign-in onboarding", () => {
  it("keeps More-only guide destinations anchored to the visible More tab on mobile", () => {
    expect(TOUR_STEPS.map((step) => step.navItem)).toEqual([
      "HOME",
      "LEAGUES",
      "CHATS",
      "MOCK DRAFT",
      "INJURY CENTER",
      "ALERTS",
      "SETTINGS",
      "SIGN OUT",
    ]);
    expect(TOUR_STEPS.slice(0, 4).map((step) => step.target)).toEqual(
      TOUR_STEPS.slice(0, 4).map((step) => `[data-guide-nav="${step.navItem}"]`),
    );
    for (const step of TOUR_STEPS.slice(4)) {
      expect(step.target).toContain(`[data-guide-nav="${step.navItem}"]`);
      expect(step.target).toContain('[data-guide-nav="MORE"]');
    }
  });

  it("honors an explicit replay request even when persistent browser storage is unavailable", () => {
    expect(shouldStartGuide(1, true)).toBe(true);
  });

  it("keeps native tour cards below the iOS status area", () => {
    expect(getTourTooltipTop(16, 844, true)).toBe(59);
    expect(getTourTooltipTop(160, 844, true)).toBe(160);
    expect(getTourTooltipTop(800, 844, true)).toBe(430);
    expect(getTourTooltipTop(16, 844, false)).toBe(16);
  });
});
