import { describe, expect, it } from "vitest";

import { TOUR_STEPS } from "./AppOnboardingTour";
import { getShellNavItems, navDomId } from "./app-shell/navigation";
import { shouldStartGuide } from "@/lib/onboarding";

describe("first-sign-in onboarding", () => {
  it("introduces every signed-in sidebar destination", () => {
    const regularNewUser = {
      id: 1,
      firstName: "New User",
      email: "new.user@example.com",
      isAdmin: false,
    };

    expect(TOUR_STEPS.map((step) => step.target)).toEqual(
      getShellNavItems(regularNewUser, true, 0, true).map((item) => `#${navDomId(item.name)}`),
    );
  });

  it("honors an explicit replay request even when persistent browser storage is unavailable", () => {
    expect(shouldStartGuide(1, true)).toBe(true);
  });
});
