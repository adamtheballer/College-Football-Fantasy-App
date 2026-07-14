import { describe, expect, it } from "vitest";

import {
  formatMatchupPoints,
  formatMatchupStatus,
  matchupStatusVariant,
  shouldShowMatchupScorePanels,
} from "./LeagueMatchup";

describe("league matchup helpers", () => {
  it("maps backend matchup statuses to honest UI labels", () => {
    expect(formatMatchupStatus("live")).toBe("Live");
    expect(formatMatchupStatus("final")).toBe("Final");
    expect(formatMatchupStatus("stat_corrected")).toBe("Corrected");
    expect(formatMatchupStatus("delayed")).toBe("Delayed");
    expect(formatMatchupStatus("unavailable")).toBe("Unavailable");
    expect(formatMatchupStatus(null)).toBe("Projected");
  });

  it("maps backend matchup statuses to semantic badge variants", () => {
    expect(matchupStatusVariant("live")).toBe("live");
    expect(matchupStatusVariant("final")).toBe("final");
    expect(matchupStatusVariant("stat_corrected")).toBe("corrected");
    expect(matchupStatusVariant("delayed")).toBe("delayed");
    expect(matchupStatusVariant("unavailable")).toBe("unavailable");
    expect(matchupStatusVariant(undefined)).toBe("projected");
  });

  it("formats matchup points with a dash when values are not real numbers", () => {
    expect(formatMatchupPoints(118.44)).toBe("118.4");
    expect(formatMatchupPoints(null)).toBe("—");
    expect(formatMatchupPoints(Number.NaN)).toBe("—");
  });

  it("hides score panels before live scoring begins", () => {
    expect(shouldShowMatchupScorePanels("projected")).toBe(false);
    expect(shouldShowMatchupScorePanels(null)).toBe(false);
    expect(shouldShowMatchupScorePanels("live")).toBe(true);
    expect(shouldShowMatchupScorePanels("final")).toBe(true);
    expect(shouldShowMatchupScorePanels("stat_corrected")).toBe(true);
  });
});
