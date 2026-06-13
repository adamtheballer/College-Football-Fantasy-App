import { describe, expect, it } from "vitest";

import { mapPlayersToDraftBoardPlayers } from "./draft-board-adapters";
import type { Player } from "@/types/player";

const makePlayer = (id: number, rank: number): Player => ({
  id,
  name: `Player ${id}`,
  school: "Test",
  pos: "QB",
  conf: "B12",
  rank,
  boardRank: rank,
  adp: rank,
  posRank: null,
  rostered: 0,
  status: "HEALTHY",
  projection: { fpts: 300 - rank },
  history: [],
  analysis: "",
});

describe("mapPlayersToDraftBoardPlayers", () => {
  it("preserves master board ranks after drafted players are removed", () => {
    const mapped = mapPlayersToDraftBoardPlayers(
      [makePlayer(1, 1), makePlayer(2, 2), makePlayer(3, 3)],
      new Set([1])
    );

    expect(mapped.map((player) => player.id)).toEqual([2, 3]);
    expect(mapped.map((player) => player.rank)).toEqual([2, 3]);
    expect(mapped.map((player) => player.boardRank)).toEqual([2, 3]);
  });
});
