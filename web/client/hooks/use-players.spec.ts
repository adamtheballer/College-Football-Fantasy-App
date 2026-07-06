import { describe, expect, it } from "vitest";

import { normalizePlayer } from "./use-players";

const basePlayer = {
  id: 1,
  name: "Projected WR",
  position: "WR",
  school: "Test State",
  sheet_projected_season_points: 100,
};

describe("normalizePlayer", () => {
  it("prefers league-specific projection points over default fantasy points", () => {
    const player = normalizePlayer(basePlayer, {
      projection: {
        player_id: 1,
        pass_yards: 0,
        pass_tds: 0,
        interceptions: 0,
        rush_yards: 0,
        rush_tds: 0,
        rec_yards: 75,
        rec_tds: 1,
        receptions: 5,
        fantasy_points: 18.5,
        league_fantasy_points: 13.5,
        floor: 9.25,
        league_floor: 6.75,
        ceiling: 27.75,
        league_ceiling: 20.25,
        boom_prob: 0.2,
        bust_prob: 0.1,
        expected_plays: 8,
        expected_rush_per_play: 0,
        expected_td_per_play: 0.125,
      },
    });

    expect(player.projection.fpts).toBe(13.5);
    expect(player.projection.floor).toBe(6.75);
    expect(player.projection.ceiling).toBe(20.25);
  });
});
