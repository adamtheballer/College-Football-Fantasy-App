import { describe, expect, it } from "vitest";
import { createLeagueScoringToApi } from "./scoringSettings";

describe("createLeagueScoringToApi", () => {
  it("converts create-league scoring form values to canonical API scoring keys", () => {
    const scoring = createLeagueScoringToApi({
      ppr: 1,
      pass_td: 4,
      pass_yds_per_pt: 25,
      rush_yds_per_pt: 10,
      rec_yds_per_pt: 10,
      rush_td: 6,
      rec_td: 6,
      int: -2,
      fumble_lost: -2,
      fg: 3,
      xp: 1,
    });

    expect(scoring).toMatchObject({
      receptions: 1,
      pass_tds: 4,
      pass_yards: 0.04,
      rush_yards: 0.1,
      rec_yards: 0.1,
      rush_tds: 6,
      rec_tds: 6,
      interceptions: -2,
      fumbles_lost: -2,
      fg_made_0_39: 3,
      xp_made: 1,
    });
    expect(scoring).not.toHaveProperty("pass_yds_per_pt");
    expect(scoring).not.toHaveProperty("rush_yds_per_pt");
    expect(scoring).not.toHaveProperty("rec_yds_per_pt");
  });

  it("does not emit invalid multipliers for zero yards-per-point values", () => {
    const scoring = createLeagueScoringToApi({
      ppr: 1,
      pass_td: 4,
      pass_yds_per_pt: 0,
      rush_yds_per_pt: 0,
      rec_yds_per_pt: 0,
      rush_td: 6,
      rec_td: 6,
      int: -2,
      fumble_lost: -2,
      fg: 3,
      xp: 1,
    });

    expect(scoring.pass_yards).toBe(0);
    expect(scoring.rush_yards).toBe(0);
    expect(scoring.rec_yards).toBe(0);
  });
});
