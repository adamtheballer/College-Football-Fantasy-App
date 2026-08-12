import { describe, expect, it } from "vitest";

import { getLeagueScheduleWeeks } from "./leagueSchedule";

describe("getLeagueScheduleWeeks", () => {
  it("returns unique, ascending regular-season weeks and excludes invalid entries", () => {
    expect(
      getLeagueScheduleWeeks([
        {
          matchup_id: 3,
          week: 13,
          home_team_id: 1,
          home_team_name: "A",
          away_team_id: 2,
          away_team_name: "B",
          home_projected_total: 0,
          away_projected_total: 0,
          home_win_probability: 50,
          away_win_probability: 50,
        },
        {
          matchup_id: 2,
          week: 1,
          home_team_id: 1,
          home_team_name: "A",
          away_team_id: 2,
          away_team_name: "B",
          home_projected_total: 0,
          away_projected_total: 0,
          home_win_probability: 50,
          away_win_probability: 50,
        },
        {
          matchup_id: 1,
          week: 1,
          home_team_id: 3,
          home_team_name: "C",
          away_team_id: 4,
          away_team_name: "D",
          home_projected_total: 0,
          away_projected_total: 0,
          home_win_probability: 50,
          away_win_probability: 50,
        },
        {
          matchup_id: 4,
          week: Number.NaN,
          home_team_id: 1,
          home_team_name: "A",
          away_team_id: 2,
          away_team_name: "B",
          home_projected_total: 0,
          away_projected_total: 0,
          home_win_probability: 50,
          away_win_probability: 50,
        },
        {
          matchup_id: 5,
          week: 0,
          home_team_id: 1,
          home_team_name: "A",
          away_team_id: 2,
          away_team_name: "B",
          home_projected_total: 0,
          away_projected_total: 0,
          home_win_probability: 50,
          away_win_probability: 50,
        },
      ]),
    ).toEqual([1, 13]);
  });
});
