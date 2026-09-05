import { describe, expect, it } from "vitest";

import {
  rankWaiverSearchResults,
  waiverOpponentLabel,
  waiverPlayerCanBeClaimed,
  waiverProjectionLabel,
  waiverSearchMatches,
  waiverWeekPoints,
} from "./LeagueWaivers";

describe("waiverProjectionLabel", () => {
  it("uses the backend projection status instead of presenting a bye as a missing projection", () => {
    expect(waiverProjectionLabel(0, "BYE")).toBe("BYE");
    expect(waiverProjectionLabel(0, "OUT")).toBe("OUT");
    expect(waiverProjectionLabel(12.34, "ACTIVE")).toBe("12.3");
    expect(waiverProjectionLabel(undefined, "UNAVAILABLE")).toBe("—");
  });
});

describe("waiverWeekPoints", () => {
  it("prefers a verified final total, including a scoreless final, over the forecast", () => {
    expect(waiverWeekPoints(18.76, 12.34, "ACTIVE")).toEqual({ label: "18.8", isFinal: true });
    expect(waiverWeekPoints(0, undefined, "UNAVAILABLE")).toEqual({ label: "0.0", isFinal: true });
  });

  it("retains the projection state when no verified final total exists", () => {
    expect(waiverWeekPoints(null, undefined, "UNAVAILABLE")).toEqual({ label: "—", isFinal: false });
  });
});

describe("waiverOpponentLabel", () => {
  it("shows the scheduled opponent and does not invent one when schedule data is unavailable", () => {
    expect(waiverOpponentLabel("Oklahoma")).toBe("Oklahoma");
    expect(waiverOpponentLabel(null)).toBe("—");
  });
});

describe("waiverSearchMatches", () => {
  it("matches player names and their own school, but never a scheduled opponent", () => {
    const georgiaPlayerFacingTennesseeState = {
      name: "Isaiah Canion",
      school: "Georgia",
      opponent: "Tennessee State",
    };

    expect(waiverSearchMatches({ name: "Mike Matthews", school: "Tennessee" }, "Tennessee")).toBe(true);
    expect(waiverSearchMatches(georgiaPlayerFacingTennesseeState, "Tennessee")).toBe(false);
    expect(waiverSearchMatches(georgiaPlayerFacingTennesseeState, "Canion")).toBe(true);
    expect(waiverSearchMatches(georgiaPlayerFacingTennesseeState, "Georgia")).toBe(true);
  });
});

describe("waiverPlayerCanBeClaimed", () => {
  it("keeps rostered All Players results research-only", () => {
    expect(waiverPlayerCanBeClaimed("waivers")).toBe(true);
    expect(waiverPlayerCanBeClaimed("free_agent")).toBe(true);
    expect(waiverPlayerCanBeClaimed("rostered")).toBe(false);
  });
});

describe("rankWaiverSearchResults", () => {
  it("places an exact school match ahead of similarly named schools without changing the remaining rank order", () => {
    const results = rankWaiverSearchResults([
      { name: "West Virginia player", school: "West Virginia" },
      { name: "Virginia Tech player", school: "Virginia Tech" },
      { name: "Virginia player", school: "Virginia" },
      { name: "Another West Virginia player", school: "West Virginia" },
    ], "Virginia");

    expect(results.map((player) => player.school)).toEqual([
      "Virginia",
      "West Virginia",
      "Virginia Tech",
      "West Virginia",
    ]);
  });
});
