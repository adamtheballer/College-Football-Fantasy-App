import { describe, expect, it } from "vitest";

import {
  didFirstLiveDraftPickStart,
  getDraftStartIntroCueKey,
  isFirstLiveDraftPick,
} from "./draftStartIntro";

const firstPick = {
  draftId: 42,
  status: "on_clock",
  currentPick: 1,
  currentPickStartedAt: "2026-08-17T19:00:00Z",
};

describe("draft start intro", () => {
  it("only permits the server-confirmed first pick timer", () => {
    expect(isFirstLiveDraftPick(firstPick)).toBe(true);
    expect(isFirstLiveDraftPick({ ...firstPick, status: "pre_draft" })).toBe(false);
    expect(isFirstLiveDraftPick({ ...firstPick, currentPick: 2 })).toBe(false);
    expect(isFirstLiveDraftPick({ ...firstPick, currentPickStartedAt: null })).toBe(false);
    expect(isFirstLiveDraftPick({ ...firstPick, draftId: null })).toBe(false);
  });

  it("uses the server start timestamp to make a draft-start cue idempotent", () => {
    expect(getDraftStartIntroCueKey(firstPick)).toBe(
      "cfb:draft-start-intro:42:2026-08-17T19:00:00Z",
    );
    expect(getDraftStartIntroCueKey({ ...firstPick, currentPickStartedAt: "2026-08-18T19:00:00Z" }))
      .not.toBe(getDraftStartIntroCueKey(firstPick));
  });

  it("only starts the cue on a transition into the first-pick timer", () => {
    expect(didFirstLiveDraftPickStart({ ...firstPick, status: "pre_draft", currentPickStartedAt: null }, firstPick)).toBe(true);
    expect(didFirstLiveDraftPickStart(firstPick, firstPick)).toBe(false);
    expect(didFirstLiveDraftPickStart(null, firstPick)).toBe(false);
  });
});
