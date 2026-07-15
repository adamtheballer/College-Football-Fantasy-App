import { describe, expect, it } from "vitest";

import {
  canJoinDraftRoom,
  formatDraftCountdown,
  getDraftCountdownParts,
  hasDraftStarted,
} from "./draftStatus";

describe("draftStatus", () => {
  it("formats a full days-hours-minutes-seconds countdown", () => {
    const now = Date.parse("2026-07-14T12:00:00Z");
    const draftTime = "2026-07-16T15:04:05Z";

    expect(formatDraftCountdown(draftTime, now)).toBe("2d 3h 4m 5s");
    expect(getDraftCountdownParts(draftTime, now)).toMatchObject({
      days: 2,
      hours: 3,
      minutes: 4,
      seconds: 5,
    });
  });

  it("does not unlock before the exact draft time", () => {
    const now = Date.parse("2026-07-14T12:00:00Z");

    expect(hasDraftStarted("2026-07-14T12:00:01Z", now)).toBe(false);
    expect(hasDraftStarted("2026-07-14T12:00:00Z", now)).toBe(true);
    expect(hasDraftStarted("2026-07-14T11:59:59Z", now)).toBe(true);
  });

  it("unlocks draft-room entry for a full league after the scheduled time", () => {
    const now = Date.parse("2026-07-14T18:20:00Z");
    const draftTime = "2026-07-14T18:20:00Z";

    expect(
      canJoinDraftRoom({
        draftDateTime: draftTime,
        memberCount: 4,
        maxTeams: 4,
        now,
      })
    ).toBe(true);
    expect(
      canJoinDraftRoom({
        draftDateTime: draftTime,
        memberCount: 3,
        maxTeams: 4,
        now,
      })
    ).toBe(false);
    expect(
      canJoinDraftRoom({
        draftDateTime: "2026-07-14T18:20:01Z",
        memberCount: 4,
        maxTeams: 4,
        now,
      })
    ).toBe(false);
  });
});
