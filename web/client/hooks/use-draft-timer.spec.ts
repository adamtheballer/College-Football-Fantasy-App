import { describe, expect, it } from "vitest";

import {
  calculateClientServerOffset,
  calculateDraftSecondsRemaining,
  calculateDraftSecondsRemainingWithOffset,
  formatDraftTime,
} from "./use-draft-timer";

describe("draft timer helpers", () => {
  it("counts down from server time", () => {
    expect(
      calculateDraftSecondsRemaining(
        "2026-06-03T12:00:00.000Z",
        "2026-06-03T12:00:30.000Z",
        Date.parse("2026-06-03T12:00:05.000Z")
      )
    ).toBe(30);
  });

  it("formats mm:ss", () => {
    expect(formatDraftTime(65)).toBe("01:05");
    expect(formatDraftTime(0)).toBe("00:00");
  });

  it("counts down as client time advances", () => {
    const offsetMs = calculateClientServerOffset(
      "2026-06-03T12:00:00.000Z",
      Date.parse("2026-06-03T12:00:00.000Z")
    );
    const expiresAt = "2026-06-03T12:00:30.000Z";

    expect(calculateDraftSecondsRemainingWithOffset(expiresAt, offsetMs, Date.parse("2026-06-03T12:00:00.000Z"))).toBe(30);
    expect(calculateDraftSecondsRemainingWithOffset(expiresAt, offsetMs, Date.parse("2026-06-03T12:00:12.000Z"))).toBe(18);
  });

  it("resets when the next pick receives a new expiry", () => {
    const clientNow = Date.parse("2026-06-03T12:00:25.000Z");
    const firstOffsetMs = calculateClientServerOffset("2026-06-03T12:00:00.000Z", Date.parse("2026-06-03T12:00:00.000Z"));
    const nextOffsetMs = calculateClientServerOffset("2026-06-03T12:00:25.000Z", clientNow);

    expect(
      calculateDraftSecondsRemainingWithOffset(
        "2026-06-03T12:00:30.000Z",
        firstOffsetMs,
        clientNow
      )
    ).toBe(5);
    expect(
      calculateDraftSecondsRemainingWithOffset(
        "2026-06-03T12:00:55.000Z",
        nextOffsetMs,
        clientNow
      )
    ).toBe(30);
  });

  it("returns expired when server expiry is past", () => {
    expect(
      calculateDraftSecondsRemaining(
        "2026-06-03T12:00:30.000Z",
        "2026-06-03T12:00:00.000Z",
        Date.parse("2026-06-03T12:00:30.000Z")
      )
    ).toBe(0);
  });
});
