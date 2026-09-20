import { describe, expect, it } from "vitest";

import { getLeagueScheduleWeeks, getScheduleScoreDisplay } from "./leagueSchedule";

describe("getLeagueScheduleWeeks", () => {
  it("returns unique, ascending regular-season weeks and excludes invalid entries", () => {
    expect(
      getLeagueScheduleWeeks([
        { matchup_id: 3, week: 13, home_team_id: 1, home_team_name: "A", away_team_id: 2, away_team_name: "B", home_projected_total: 0, away_projected_total: 0, home_win_probability: 50, away_win_probability: 50 },
        { matchup_id: 2, week: 1, home_team_id: 1, home_team_name: "A", away_team_id: 2, away_team_name: "B", home_projected_total: 0, away_projected_total: 0, home_win_probability: 50, away_win_probability: 50 },
        { matchup_id: 1, week: 1, home_team_id: 3, home_team_name: "C", away_team_id: 4, away_team_name: "D", home_projected_total: 0, away_projected_total: 0, home_win_probability: 50, away_win_probability: 50 },
        { matchup_id: 4, week: Number.NaN, home_team_id: 1, home_team_name: "A", away_team_id: 2, away_team_name: "B", home_projected_total: 0, away_projected_total: 0, home_win_probability: 50, away_win_probability: 50 },
        { matchup_id: 5, week: 0, home_team_id: 1, home_team_name: "A", away_team_id: 2, away_team_name: "B", home_projected_total: 0, away_projected_total: 0, home_win_probability: 50, away_win_probability: 50 },
      ])
    ).toEqual([1, 13]);
  });
});

describe("getScheduleScoreDisplay", () => {
  const row = {
    matchup_id: 1,
    week: 1,
    home_team_id: 1,
    home_team_name: "Home",
    away_team_id: 2,
    away_team_name: "Away",
    home_projected_total: null,
    away_projected_total: null,
    home_win_probability: 50,
    away_win_probability: 50,
  };

  it("uses final totals and server-certified W/L results after a matchup is complete", () => {
    const finalRow = {
      ...row,
      status: "final",
      home_current_total: 104.25,
      away_current_total: 87.5,
      home_result: "W" as const,
      away_result: "L" as const,
    };

    expect(getScheduleScoreDisplay(finalRow, "home")).toEqual({ label: "Final", total: 104.25, result: "W", isLive: false });
    expect(getScheduleScoreDisplay(finalRow, "away")).toEqual({ label: "Final", total: 87.5, result: "L", isLive: false });
  });

  it("uses the current score while a matchup is live", () => {
    expect(getScheduleScoreDisplay({ ...row, status: "live", home_current_total: 31.5 }, "home")).toEqual({
      label: "Live", total: 31.5, result: null, isLive: true,
    });
  });

  it("uses projections only before the matchup begins", () => {
    expect(getScheduleScoreDisplay({ ...row, status: "projected", home_projected_total: 118.2 }, "home")).toEqual({
      label: "Proj", total: 118.2, result: null, isLive: false,
    });
  });
});
