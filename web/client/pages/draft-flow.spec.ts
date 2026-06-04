import { describe, expect, it } from "vitest";

import { getCompletedDraftExitPath, isDraftAutoPickDue, shouldShowDraftCompletionModal } from "./draft-flow";

describe("draft page flow helpers", () => {
  it("flags expired live pick clocks for auto-pick", () => {
    expect(
      isDraftAutoPickDue({
        draftRoom: {
          status: "live",
          isComplete: false,
          currentTeamId: 12,
          phaseType: "pick_clock",
        },
        isExpired: true,
        autoPickPending: false,
      })
    ).toBe(true);
  });

  it("does not auto-pick while pending or complete", () => {
    expect(
      isDraftAutoPickDue({
        draftRoom: {
          status: "live",
          isComplete: false,
          currentTeamId: 12,
          phaseType: "pick_clock",
        },
        isExpired: true,
        autoPickPending: true,
      })
    ).toBe(false);

    expect(
      isDraftAutoPickDue({
        draftRoom: {
          status: "completed",
          isComplete: true,
          currentTeamId: null,
          phaseType: "complete",
        },
        isExpired: true,
        autoPickPending: false,
      })
    ).toBe(false);
  });

  it("shows the completion modal until dismissed", () => {
    expect(shouldShowDraftCompletionModal({ isComplete: true, dismissed: false })).toBe(true);
    expect(shouldShowDraftCompletionModal({ isComplete: true, dismissed: true })).toBe(false);
    expect(shouldShowDraftCompletionModal({ isComplete: false, dismissed: false })).toBe(false);
  });

  it("exits completed mock drafts to the draft hub", () => {
    expect(getCompletedDraftExitPath()).toBe("/draft");
  });
});
