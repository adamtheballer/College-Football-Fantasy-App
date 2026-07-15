import { describe, expect, it } from "vitest";

import { isLeaguePostDraft, shouldRestrictLeagueToDraft } from "./leagueLifecycle";

describe("leagueLifecycle", () => {
  it("keeps scheduled and live leagues restricted to the draft tab", () => {
    expect(shouldRestrictLeagueToDraft({ draftStatus: "scheduled", leagueStatus: "active" })).toBe(true);
    expect(shouldRestrictLeagueToDraft({ draftStatus: "live", leagueStatus: "draft_scheduled" })).toBe(true);
  });

  it("opens full league navigation after the draft is complete", () => {
    expect(isLeaguePostDraft({ draftStatus: "complete", leagueStatus: "active" })).toBe(true);
    expect(shouldRestrictLeagueToDraft({ draftStatus: "completed", leagueStatus: "active" })).toBe(false);
  });
});
