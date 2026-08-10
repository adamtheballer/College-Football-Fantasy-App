import { describe, expect, it } from "vitest";

import {
  FIRST_CENTERED_DRAFT_PICK,
  getCenteredDraftOrderScrollLeft,
} from "./draftOrderCarousel";

describe("draft order carousel", () => {
  it("keeps the first three picks at the start of the rail", () => {
    expect(FIRST_CENTERED_DRAFT_PICK).toBe(4);
    expect(
      getCenteredDraftOrderScrollLeft({
        overallPick: 3,
        cardOffsetLeft: 400,
        cardWidth: 180,
        containerWidth: 600,
      }),
    ).toBe(0);
  });

  it("centers the active manager from pick four onward", () => {
    expect(
      getCenteredDraftOrderScrollLeft({
        overallPick: 4,
        cardOffsetLeft: 720,
        cardWidth: 180,
        containerWidth: 600,
      }),
    ).toBe(510);
  });
});
