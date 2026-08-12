import { describe, expect, it } from "vitest";

import {
  isLeaguePostDraft,
  shouldRestrictLeagueToDraft,
  shouldShowLeagueDraftRoomAction,
} from "./leagueLifecycle";

describe("leagueLifecycle", () => {
  it("keeps scheduled and live leagues restricted to the draft tab", () => {
    expect(
      shouldRestrictLeagueToDraft({
        draftStatus: "scheduled",
        leagueStatus: "active",
      }),
    ).toBe(true);
    expect(
      shouldRestrictLeagueToDraft({
        draftStatus: "live",
        leagueStatus: "draft_scheduled",
      }),
    ).toBe(true);
  });

  it("opens full league navigation after the draft is complete", () => {
    expect(
      isLeaguePostDraft({ draftStatus: "complete", leagueStatus: "active" }),
    ).toBe(true);
    expect(
      shouldRestrictLeagueToDraft({
        draftStatus: "completed",
        leagueStatus: "active",
      }),
    ).toBe(false);
  });

  it("never exposes a draft-room action after draft completion, even when the old draft timestamp remains", () => {
    expect(
      shouldShowLeagueDraftRoomAction({
        draftStatus: "completed",
        leagueStatus: "post_draft",
        draftDateTime: "2026-07-17T23:00:00Z",
      }),
    ).toBe(false);
    expect(
      shouldShowLeagueDraftRoomAction({
        draftStatus: "scheduled",
        leagueStatus: "draft_scheduled",
        draftDateTime: "2026-08-01T23:00:00Z",
      }),
    ).toBe(true);
  });
});
