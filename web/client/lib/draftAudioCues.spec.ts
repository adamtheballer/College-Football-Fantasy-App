import { describe, expect, it } from "vitest";

import {
  DRAFT_AUDIO_URLS,
  getDraftAudioCueKey,
  isActiveUserPick,
  shouldPlayDraftStartCue,
  shouldPlayUserCountdownCue,
  shouldPlayUserFirstPickCue,
} from "./draftAudioCues";

const preDraft = {
  draftId: 42,
  status: "pre_draft",
  currentPick: 1,
  currentPickStartedAt: null,
  currentTeamId: 9,
  userTeamId: 9,
};

const firstOverallPick = {
  ...preDraft,
  status: "on_clock",
  currentPickStartedAt: "2026-08-23T19:00:00Z",
};

describe("real-draft audio cues", () => {
  it("uses separate shipped assets for draft start, the user's first pick, and their countdown", () => {
    expect(DRAFT_AUDIO_URLS).toEqual({
      start: "/audio/cfb-draft-start.wav",
      userFirstPick: "/audio/cfb-draft-user-first-pick.wav",
      userCountdown: "/audio/cfb-draft-user-countdown-10.wav",
    });
  });

  it("plays the start cue only when the authoritative first timer begins", () => {
    expect(shouldPlayDraftStartCue(preDraft, firstOverallPick)).toBe(true);
    expect(shouldPlayDraftStartCue(firstOverallPick, firstOverallPick)).toBe(false);
    expect(shouldPlayDraftStartCue(null, firstOverallPick)).toBe(false);
  });

  it("plays the user's first-pick cue for their first non-first-overall turn", () => {
    const userFirstPick = {
      ...firstOverallPick,
      currentPick: 2,
      currentPickStartedAt: "2026-08-23T19:00:08Z",
    };
    expect(shouldPlayUserFirstPickCue({ previous: firstOverallPick, current: userFirstPick, completedUserPickCount: 0 })).toBe(true);
    expect(shouldPlayUserFirstPickCue({ previous: preDraft, current: firstOverallPick, completedUserPickCount: 0 })).toBe(false);
    expect(shouldPlayUserFirstPickCue({ previous: firstOverallPick, current: userFirstPick, completedUserPickCount: 1 })).toBe(false);
  });

  it("plays the ten-second cue only on the viewer's live turn", () => {
    expect(shouldPlayUserCountdownCue({ current: firstOverallPick, secondsRemaining: 10 })).toBe(true);
    expect(shouldPlayUserCountdownCue({ current: { ...firstOverallPick, currentTeamId: 8 }, secondsRemaining: 10 })).toBe(false);
    expect(shouldPlayUserCountdownCue({ current: firstOverallPick, secondsRemaining: 9 })).toBe(false);
  });

  it("keys each cue to the authoritative pick start so polling cannot replay it", () => {
    expect(getDraftAudioCueKey("userCountdown", firstOverallPick)).toBe(
      "cfb:draft-audio:userCountdown:42:1:2026-08-23T19:00:00Z",
    );
  });

  it("recognizes the user's team from IDs, not display names", () => {
    expect(isActiveUserPick(firstOverallPick)).toBe(true);
    expect(isActiveUserPick({ ...firstOverallPick, userTeamId: 10 })).toBe(false);
  });
});
