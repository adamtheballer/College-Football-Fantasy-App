import { describe, expect, it } from "vitest";

import {
  leagueLocalDateTimeToUtc,
  toLeagueDateTimeLocalValue,
} from "./draftSchedule";

describe("draftSchedule", () => {
  it("uses the league timezone rather than the browser timezone for picker values", () => {
    expect(
      toLeagueDateTimeLocalValue("2026-08-20T23:30:00Z", "America/New_York"),
    ).toBe("2026-08-20T19:30");
    expect(
      leagueLocalDateTimeToUtc("2026-08-20T19:30", "America/New_York"),
    ).toEqual({
      iso: "2026-08-20T23:30:00.000Z",
    });
  });

  it("rejects non-existent and ambiguous daylight-saving local times", () => {
    expect(
      leagueLocalDateTimeToUtc("2026-03-08T02:30", "America/New_York"),
    ).toMatchObject({
      error: expect.stringContaining("does not exist"),
    });
    expect(
      leagueLocalDateTimeToUtc("2026-11-01T01:30", "America/New_York"),
    ).toMatchObject({
      error: expect.stringContaining("occurs twice"),
    });
  });
});
