import { describe, expect, it } from "vitest";

import {
  LIVE_MATCHUP_REFRESH_MS,
  hasLiveRosteredPlayer,
  hasUpcomingRosteredKickoff,
  matchupRefreshCountdownSeconds,
  matchupRefreshInterval,
} from "./use-leagues";

describe("matchup live refresh cadence", () => {
  it("keeps the three-minute cycle for a stale live matchup", () => {
    const data = {
      status: "live",
      live_scoring_freshness: { state: "stale" },
    } as any;

    expect(matchupRefreshInterval(data)).toBe(LIVE_MATCHUP_REFRESH_MS);
    expect(matchupRefreshCountdownSeconds(data, 10_000, 10_000)).toBe(180);
  });

  it("starts the three-minute countdown from the successful matchup response", () => {
    const now = Date.UTC(2026, 7, 29, 20, 0, 0);
    const data = {
      status: "live",
      live_scoring_freshness: { state: "fresh" },
      next_refresh_at: new Date(now + LIVE_MATCHUP_REFRESH_MS).toISOString(),
    } as any;

    expect(matchupRefreshInterval(data)).toBe(LIVE_MATCHUP_REFRESH_MS);
    expect(matchupRefreshCountdownSeconds(data, now, now)).toBe(180);
  });

  it("refreshes for a live bench player even when the starter-only matchup is still projected", () => {
    const data = {
      status: "projected",
      my_roster: [{ is_starter: false, live_game_state: "live", live_scoring_status: "live" }],
      opponent_roster: [],
    } as any;

    expect(hasLiveRosteredPlayer(data)).toBe(true);
    expect(matchupRefreshInterval(data)).toBe(LIVE_MATCHUP_REFRESH_MS);
    expect(matchupRefreshCountdownSeconds(data, 10_000, 10_000)).toBe(180);
  });

  it("begins the three-minute live refresh cycle at kickoff before a provider play arrives", () => {
    const now = Date.UTC(2026, 7, 29, 23, 0, 0);
    const data = {
      status: "projected",
      my_roster: [{
        is_starter: false,
        live_game_state: "scheduled",
        game_start_at: new Date(now - 1_000).toISOString(),
      }],
      opponent_roster: [],
    } as any;

    expect(hasLiveRosteredPlayer(data, now)).toBe(true);
    expect(hasUpcomingRosteredKickoff(data, now)).toBe(false);
    expect(matchupRefreshInterval(data, now)).toBe(LIVE_MATCHUP_REFRESH_MS);
    expect(matchupRefreshCountdownSeconds(data, now, now)).toBe(180);
  });
});
