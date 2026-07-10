import { describe, expect, it } from "vitest";

import {
  canOpenRosterPlayerCard,
  createBlankRosterRows,
  createEmptyRosterSlotRows,
  isPlaceholderRosterPlayer,
  rosterProjectionTotal,
  shouldBlankRoster,
  visibleRosterPlayers,
} from "./rosterDisplay";

describe("rosterDisplay", () => {
  it("excludes placeholder preview rows from projection totals", () => {
    const players = [
      {
        player_id: 101,
        player_name: "QB Starter Preview",
        projected_points: 22.4,
        weekly_projected_fantasy_points: 22.4,
      },
      {
        player_id: 102,
        player_name: "RB Flex Preview",
        projected_points: 14.2,
        weekly_projected_fantasy_points: 14.2,
      },
    ];

    expect(rosterProjectionTotal(players)).toBeNull();
  });

  it("blanks placeholder-only pre-draft roster rows instead of rendering fake projections", () => {
    const players = [
      {
        player_id: 101,
        player_name: "QB Starter Preview",
        projected_points: 22.4,
        weekly_projected_fantasy_points: 22.4,
      },
      {
        player_id: 102,
        player_name: "RB Starter Preview",
        projected_points: 17.8,
        weekly_projected_fantasy_points: 17.8,
      },
      {
        player_id: 103,
        player_name: "Bench Preview",
        projected_points: 34.5,
        weekly_projected_fantasy_points: 34.5,
      },
    ];

    expect(shouldBlankRoster(players)).toBe(true);
    expect(visibleRosterPlayers(players, shouldBlankRoster(players))).toEqual([]);
    expect(rosterProjectionTotal(players, shouldBlankRoster(players))).toBeNull();
  });

  it("blanks rows when the API marks the roster as empty even if rows contain projections", () => {
    const players = [
      {
        player_id: 101,
        player_name: "QB Starter Preview",
        projected_points: 22.4,
        weekly_projected_fantasy_points: 22.4,
      },
      {
        player_id: 102,
        player_name: "RB Flex Preview",
        projected_points: 14.6,
        weekly_projected_fantasy_points: 14.6,
      },
    ];
    const forceBlank = shouldBlankRoster(players, {
      message: "Roster is empty. It will populate after the draft.",
    });

    expect(forceBlank).toBe(true);
    expect(visibleRosterPlayers(players, forceBlank)).toEqual([]);
    expect(rosterProjectionTotal(players, forceBlank)).toBeNull();
  });

  it("blanks the old placeholder-roster message instead of trusting stale projected rows", () => {
    const players = [
      {
        player_id: 101,
        player_name: "QB Starter Preview",
        projected_points: 22.4,
        weekly_projected_fantasy_points: 22.4,
      },
      {
        player_id: 102,
        player_name: "RB Starter Preview",
        projected_points: 17.8,
        weekly_projected_fantasy_points: 17.8,
      },
      {
        player_id: 103,
        player_name: "Bench Preview",
        projected_points: 34.5,
        weekly_projected_fantasy_points: 34.5,
      },
    ];
    const forceBlank = shouldBlankRoster(players, {
      message: "Week 1 placeholder roster is shown until this league imports real draft results.",
    });

    expect(forceBlank).toBe(true);
    expect(visibleRosterPlayers(players, forceBlank)).toEqual([]);
    expect(rosterProjectionTotal(players, forceBlank)).toBeNull();
  });

  it("does not treat rows without valid player IDs as real roster players", () => {
    const players = [
      {
        player_id: null,
        player_name: "Loaded Name Without Real Player ID",
        projected_points: 122.8,
        weekly_projected_fantasy_points: 122.8,
      },
    ];

    expect(shouldBlankRoster(players)).toBe(true);
    expect(rosterProjectionTotal(players)).toBeNull();
    expect(canOpenRosterPlayerCard(players[0])).toBe(false);
  });

  it("force-blanks real-looking rows before draft completion", () => {
    const players = [
      {
        player_id: 101,
        player_name: "Real Player",
        projected_points: 122.8,
        weekly_projected_fantasy_points: 122.8,
      },
    ];

    expect(rosterProjectionTotal(players, true)).toBeNull();
    expect(canOpenRosterPlayerCard(players[0], true)).toBe(false);
  });

  it("allows cards and totals only for actual rostered players", () => {
    const player = {
      player_id: 101,
      player_name: "Actual Roster Player",
      projected_points: 18.5,
      weekly_projected_fantasy_points: 18.5,
      status: "active",
    };

    expect(isPlaceholderRosterPlayer(player)).toBe(false);
    expect(canOpenRosterPlayerCard(player)).toBe(true);
    expect(rosterProjectionTotal([player])).toBe(18.5);
  });

  it("does not open cards for empty or fake player IDs", () => {
    expect(canOpenRosterPlayerCard({ player_id: null, player_name: "" })).toBe(false);
    expect(canOpenRosterPlayerCard({ player_id: -1, player_name: "Placeholder" })).toBe(false);
  });

  it("builds disabled empty roster slots without player IDs or projections", () => {
    const rows = createEmptyRosterSlotRows({
      rosterSlotLimits: { QB: 1, RB: 2, BENCH: 1 },
      fantasyTeamId: 10,
      fantasyTeamName: "Adam's Team",
      leagueId: 99,
    });

    expect(rows).toHaveLength(4);
    expect(rows.map((row) => row.slot)).toEqual(["QB", "RB", "RB", "BENCH"]);
    expect(rows.every((row) => row.player_name === "N/A")).toBe(true);
    expect(rows.every((row) => row.player_id === null)).toBe(true);
    expect(rows.every((row) => row.projected_points === null)).toBe(true);
    expect(rows.every((row) => row.weekly_projected_fantasy_points === null)).toBe(true);
    expect(rows.every((row) => isPlaceholderRosterPlayer(row))).toBe(true);
    expect(rows.every((row) => !canOpenRosterPlayerCard(row))).toBe(true);
    expect(rosterProjectionTotal(rows)).toBeNull();
  });

  it("builds blank roster rows from BE bench aliases", () => {
    const rows = createEmptyRosterSlotRows({
      rosterSlotLimits: { QB: 1, BE: 2 },
      fantasyTeamId: 10,
      fantasyTeamName: "Adam's Team",
      leagueId: 99,
    });

    expect(rows.map((row) => row.slot)).toEqual(["QB", "BENCH", "BENCH"]);
    expect(rows.every((row) => row.player_name === "N/A")).toBe(true);
    expect(rows.every((row) => row.player_id === null)).toBe(true);
    expect(rows.every((row) => row.projected_points === null)).toBe(true);
  });

  it("falls back to existing slot layout while removing fake player data", () => {
    const rows = createBlankRosterRows({
      players: [
        {
          id: 101,
          fantasy_team_id: 10,
          fantasy_team_name: "Adam's Team",
          player_id: 501,
          player_name: "QB Starter Preview",
          school: "Week 1 Preview",
          position: "QB",
          roster_slot: "QB",
          opponent: "TBD",
          projected_points: 22.4,
          weekly_projected_fantasy_points: 22.4,
        },
      ],
      fantasyTeamId: 10,
      fantasyTeamName: "Adam's Team",
      leagueId: 99,
    });

    expect(rows).toHaveLength(1);
    expect(rows[0].player_name).toBe("N/A");
    expect(rows[0].school).toBeNull();
    expect(rows[0].position).toBe("QB");
    expect(rows[0].roster_slot).toBe("QB");
    expect(rows[0].player_id).toBeNull();
    expect(rows[0].projected_points).toBeNull();
    expect(rows[0].weekly_projected_fantasy_points).toBeNull();
    expect(canOpenRosterPlayerCard(rows[0])).toBe(false);
    expect(rosterProjectionTotal(rows)).toBeNull();
  });
});
