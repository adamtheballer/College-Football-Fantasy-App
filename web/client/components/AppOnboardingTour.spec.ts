import { describe, expect, it } from "vitest";

import { getTourTooltipTop, TOUR_STEPS } from "./AppOnboardingTour";
import { shouldStartGuide } from "@/lib/onboarding";

describe("first-sign-in onboarding", () => {
  it("keeps the first session to three useful, skippable steps", () => {
    expect(TOUR_STEPS.map((step) => step.navItem)).toEqual([
      "HOME",
      "CHALLENGES",
      "LEAGUES",
    ]);
    expect(TOUR_STEPS[1].target).toContain("data-guide-challenges");
    expect(TOUR_STEPS[1].description).toContain("Submit");
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
