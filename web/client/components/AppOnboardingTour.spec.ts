import { describe, expect, it } from "vitest";

import { TOUR_STEPS } from "./AppOnboardingTour";
import { getShellNavItems, navDomId } from "./app-shell/navigation";

describe("first-sign-in onboarding", () => {
  it("introduces every signed-in sidebar destination", () => {
    const regularNewUser = {
      id: 1,
      firstName: "New User",
      email: "new.user@example.com",
      isAdmin: false,
    };

    const navigationTargets = getShellNavItems(regularNewUser, true, 0, true)
      .map((item) => `#${navDomId(item.name)}`);

    expect(TOUR_STEPS.map((step) => step.target)).toEqual([
      ...navigationTargets.slice(0, 2),
      "#dashboard-saturday-pick-6",
      ...navigationTargets.slice(2),
    ]);
  });
});
