import { describe, expect, it } from "vitest";

import {
  DEGRADED_MATCHUP_REFRESH_MS,
  LIVE_MATCHUP_REFRESH_MS,
  matchupRefreshCountdownSeconds,
  matchupRefreshInterval,
} from "./use-leagues";

describe("matchup live refresh cadence", () => {
  it("rechecks a stale live matchup quickly instead of waiting for the normal provider cadence", () => {
    const data = {
      status: "live",
      live_scoring_freshness: { state: "stale" },
    } as any;

    expect(matchupRefreshInterval(data, 10_000)).toBe(DEGRADED_MATCHUP_REFRESH_MS);
    expect(matchupRefreshCountdownSeconds(data, 10_000, 10_000)).toBe(10);
  });

  it("uses the provider's next snapshot time for a healthy live matchup", () => {
    const now = Date.UTC(2026, 7, 29, 20, 0, 0);
    const data = {
      status: "live",
      live_scoring_freshness: { state: "fresh" },
      next_refresh_at: new Date(now + LIVE_MATCHUP_REFRESH_MS).toISOString(),
    } as any;

    expect(matchupRefreshInterval(data, now)).toBe(LIVE_MATCHUP_REFRESH_MS);
    expect(matchupRefreshCountdownSeconds(data, now, now)).toBe(180);
  });
});
