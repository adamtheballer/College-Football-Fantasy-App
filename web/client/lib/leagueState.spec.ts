import { describe, expect, it } from "vitest";

import { isPostDraftLeague, isPreDraftLeague } from "./leagueState";
import type { LeagueSettingsTabResponse } from "@/types/league";

const settings = (
  leagueStatus: string | null,
  draftStatus: string | null
) =>
  ({
    league_status: leagueStatus,
    draft_status: draftStatus,
    league_info: {
      status: leagueStatus,
      draft_status: draftStatus,
    },
  }) as unknown as LeagueSettingsTabResponse;

describe("leagueState", () => {
  it("treats active leagues with scheduled drafts as pre-draft", () => {
    const state = settings("active", "scheduled");

    expect(isPreDraftLeague(state)).toBe(true);
    expect(isPostDraftLeague(state)).toBe(false);
  });

  it("treats completed drafts as post-draft regardless of league status", () => {
    const state = settings("active", "completed");

    expect(isPreDraftLeague(state)).toBe(false);
    expect(isPostDraftLeague(state)).toBe(true);
  });
});
