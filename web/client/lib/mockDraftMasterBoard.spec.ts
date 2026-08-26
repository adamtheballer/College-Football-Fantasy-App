import { describe, expect, it } from "vitest";

import { mergeMockDraftMasterBoardPlayers } from "@/lib/mockDraftMasterBoard";
import type { Player } from "@/types/player";

const makePlayer = (overrides: Partial<Player>): Player => ({
  id: 1,
  name: "Approved Player",
  school: "Ohio State",
  pos: "WR",
  conf: "BIG10",
  rank: 1,
  boardRank: 1,
  adp: 1,
  posRank: 1,
  rostered: 0,
  status: "HEALTHY",
  projection: { fpts: 250 },
  history: [],
  analysis: "",
  sheetSourceSheetId: "snapshot:2026:Big10",
  sheetProjectedSeasonPoints: 250,
  ...overrides,
});

describe("mock draft master board player source", () => {
  it("uses only the approved API player pool and never manufactures CFB27 rows", () => {
    const approved = makePlayer({ id: 42, name: "Jeremiah Smith", school: "Ohio State" });

    const boardPlayers = mergeMockDraftMasterBoardPlayers([approved]);

    expect(boardPlayers).toEqual([approved]);
    expect(boardPlayers.find((player) => player.name === "Easton Messer")).toBeUndefined();
    expect(boardPlayers.find((player) => player.school === "FAU")).toBeUndefined();
  });

  it("does not invent a fallback player when the approved player pool is empty", () => {
    expect(mergeMockDraftMasterBoardPlayers([])).toEqual([]);
  });

  it("preserves official availability so mock draft rows use the same status marker as real drafts", () => {
    const outPlayer = makePlayer({ id: 1594, name: "Ahmad Hardy", school: "Missouri", pos: "RB", status: "OUT" });

    expect(mergeMockDraftMasterBoardPlayers([outPlayer])[0].status).toBe("OUT");
  });
});
