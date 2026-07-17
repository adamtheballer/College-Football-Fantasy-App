import { describe, expect, it } from "vitest";

import {
  getDraftPlayerPoolBackendLimit,
  getDraftPlayerPoolPageOffsets,
  normalizePlayer,
} from "./use-players";

describe("getDraftPlayerPoolBackendLimit", () => {
  it("never exceeds the backend /players API page limit", () => {
    expect(getDraftPlayerPoolBackendLimit(200)).toBe(100);
    expect(getDraftPlayerPoolBackendLimit(100)).toBe(100);
    expect(getDraftPlayerPoolBackendLimit(12)).toBe(12);
  });
});

describe("getDraftPlayerPoolPageOffsets", () => {
  it("keeps finite page loading when fetchAll is not requested", () => {
    expect(
      getDraftPlayerPoolPageOffsets({
        fetchAll: false,
        limit: 100,
        offset: 0,
        pages: 5,
        total: 1200,
      })
    ).toEqual([0, 100, 200, 300, 400]);
  });

  it("loads every page needed for the full draft pool when fetchAll is requested", () => {
    expect(
      getDraftPlayerPoolPageOffsets({
        fetchAll: true,
        limit: getDraftPlayerPoolBackendLimit(200),
        offset: 0,
        total: 1200,
      })
    ).toEqual([0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100]);
  });

  it("splits a 200-player draft board request into valid 100-row backend pages", () => {
    const backendLimit = getDraftPlayerPoolBackendLimit(200);

    expect(backendLimit).toBe(100);
    expect(
      getDraftPlayerPoolPageOffsets({
        fetchAll: true,
        limit: backendLimit,
        offset: 0,
        total: 201,
      })
    ).toEqual([0, 100, 200]);
  });

  it("caps fetchAll requests to prevent runaway page loading", () => {
    expect(
      getDraftPlayerPoolPageOffsets({
        fetchAll: true,
        limit: 100,
        maxPages: 3,
        offset: 0,
        total: 1200,
      })
    ).toEqual([0, 100, 200]);
  });
});

describe("normalizePlayer", () => {
  it("uses the weekly projection when the draft pool supplies one", () => {
    const player = normalizePlayer(
      { id: 1, name: "Projected Player", position: "QB", school: "Georgia" },
      {
        projection: {
          player_id: 1,
          pass_yards: 260,
          pass_tds: 2,
          interceptions: 1,
          rush_yards: 30,
          rush_tds: 0,
          rec_yards: 0,
          rec_tds: 0,
          receptions: 0,
          fantasy_points: 24.6,
          floor: 16,
          ceiling: 34,
          boom_prob: 0.3,
          bust_prob: 0.15,
          expected_plays: 68,
          expected_rush_per_play: 3.5,
          expected_td_per_play: 0.04,
        },
      }
    );

    expect(player.projection.fpts).toBe(24.6);
    expect(player.projection.passingYards).toBe(260);
    expect(player.hasWeeklyProjection).toBe(true);
  });

  it("marks players without a weekly projection so draft views can avoid fake values", () => {
    const player = normalizePlayer({
      id: 2,
      name: "Unprojected Player",
      position: "WR",
      school: "Georgia",
    });

    expect(player.hasWeeklyProjection).toBe(false);
  });
});
