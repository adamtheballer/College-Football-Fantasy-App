import { describe, expect, it } from "vitest";

import {
  assignBestRosterSlotForPosition,
  canPositionFitRoster,
  filterDraftablePlayers,
  getLegalPositionsForRoster,
  getOpenSlots,
  type DraftablePlayer,
  type RosterPlayer,
  type RosterSlotLimits,
} from "./rosterLegality";

const limits: RosterSlotLimits = {
  QB: 1,
  RB: 2,
  WR: 2,
  TE: 1,
  FLEX: 1,
  K: 1,
  BENCH: 5,
};

const rosterPlayer = (id: number, position: string, assignedSlot: string): RosterPlayer => ({
  id,
  position,
  assignedSlot,
});

const draftPlayer = (id: number, pos: string): DraftablePlayer => ({ id, pos });

describe("rosterLegality", () => {
  it("only allows kickers when every other slot and bench is full", () => {
    const roster = [
      rosterPlayer(1, "QB", "QB"),
      rosterPlayer(2, "RB", "RB"),
      rosterPlayer(3, "RB", "RB"),
      rosterPlayer(4, "WR", "WR"),
      rosterPlayer(5, "WR", "WR"),
      rosterPlayer(6, "TE", "TE"),
      rosterPlayer(7, "RB", "FLEX"),
      rosterPlayer(8, "QB", "BENCH"),
      rosterPlayer(9, "RB", "BENCH"),
      rosterPlayer(10, "WR", "BENCH"),
      rosterPlayer(11, "TE", "BENCH"),
      rosterPlayer(12, "WR", "BENCH"),
    ];

    expect(getOpenSlots(roster, limits).K).toBe(1);
    expect(getLegalPositionsForRoster(roster, limits)).toEqual(["K"]);
    expect(canPositionFitRoster("QB", roster, limits)).toBe(false);
    expect(canPositionFitRoster("RB", roster, limits)).toBe(false);
    expect(canPositionFitRoster("WR", roster, limits)).toBe(false);
    expect(canPositionFitRoster("TE", roster, limits)).toBe(false);
    expect(canPositionFitRoster("K", roster, limits)).toBe(true);

    const players = [
      draftPlayer(100, "QB"),
      draftPlayer(101, "RB"),
      draftPlayer(102, "WR"),
      draftPlayer(103, "TE"),
      draftPlayer(104, "K"),
    ];
    expect(filterDraftablePlayers(players, roster, limits, new Set()).map((player) => player.pos)).toEqual(["K"]);
    expect(assignBestRosterSlotForPosition("K", roster, limits)).toBe("K");
  });

  it("allows every position when starters are full but bench has room", () => {
    const roster = [
      rosterPlayer(1, "QB", "QB"),
      rosterPlayer(2, "RB", "RB"),
      rosterPlayer(3, "RB", "RB"),
      rosterPlayer(4, "WR", "WR"),
      rosterPlayer(5, "WR", "WR"),
      rosterPlayer(6, "TE", "TE"),
      rosterPlayer(7, "RB", "FLEX"),
      rosterPlayer(8, "K", "K"),
    ];

    expect(getLegalPositionsForRoster(roster, limits)).toEqual(["QB", "RB", "WR", "TE", "K"]);
    expect(assignBestRosterSlotForPosition("QB", roster, limits)).toBe("BENCH");
  });

  it("allows only flex-eligible positions when flex is open and bench is full", () => {
    const roster = [
      rosterPlayer(1, "QB", "QB"),
      rosterPlayer(2, "RB", "RB"),
      rosterPlayer(3, "RB", "RB"),
      rosterPlayer(4, "WR", "WR"),
      rosterPlayer(5, "WR", "WR"),
      rosterPlayer(6, "TE", "TE"),
      rosterPlayer(7, "K", "K"),
      ...Array.from({ length: 5 }, (_, index) => rosterPlayer(20 + index, "WR", "BENCH")),
    ];

    expect(getLegalPositionsForRoster(roster, limits)).toEqual(["RB", "WR", "TE"]);
    expect(canPositionFitRoster("QB", roster, limits)).toBe(false);
    expect(canPositionFitRoster("K", roster, limits)).toBe(false);
  });

  it("allows only the open starter position when bench and flex are full", () => {
    const roster = [
      rosterPlayer(1, "QB", "QB"),
      rosterPlayer(2, "RB", "RB"),
      rosterPlayer(4, "WR", "WR"),
      rosterPlayer(5, "WR", "WR"),
      rosterPlayer(6, "TE", "TE"),
      rosterPlayer(7, "RB", "FLEX"),
      rosterPlayer(8, "K", "K"),
      ...Array.from({ length: 5 }, (_, index) => rosterPlayer(20 + index, "WR", "BENCH")),
    ];

    expect(getLegalPositionsForRoster(roster, limits)).toEqual(["RB"]);
  });

  it("allows quarterbacks through superflex when enabled", () => {
    const roster = [
      rosterPlayer(1, "QB", "QB"),
      ...Array.from({ length: 5 }, (_, index) => rosterPlayer(20 + index, "WR", "BENCH")),
    ];
    const superflexLimits = { ...limits, SUPERFLEX: 1 };

    expect(assignBestRosterSlotForPosition("QB", roster, superflexLimits, { superflexEnabled: true })).toBe("SUPERFLEX");
  });

  it("blocks every position when roster is full and excludes drafted players", () => {
    const roster = [
      rosterPlayer(1, "QB", "QB"),
      rosterPlayer(2, "RB", "RB"),
      rosterPlayer(3, "RB", "RB"),
      rosterPlayer(4, "WR", "WR"),
      rosterPlayer(5, "WR", "WR"),
      rosterPlayer(6, "TE", "TE"),
      rosterPlayer(7, "RB", "FLEX"),
      rosterPlayer(8, "K", "K"),
      ...Array.from({ length: 5 }, (_, index) => rosterPlayer(20 + index, "WR", "BENCH")),
    ];

    expect(getLegalPositionsForRoster(roster, limits)).toEqual([]);
    expect(filterDraftablePlayers([draftPlayer(100, "K")], roster, limits, new Set())).toEqual([]);
    expect(filterDraftablePlayers([draftPlayer(100, "K")], [], limits, new Set([100]))).toEqual([]);
  });
});
