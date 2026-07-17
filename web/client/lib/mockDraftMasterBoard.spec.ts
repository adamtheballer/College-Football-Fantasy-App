import { describe, expect, it } from "vitest";

import {
  createMissingCfb27MockDraftPlayers,
  enrichCfb27DraftPlayers,
  mergeMockDraftMasterBoardPlayers,
} from "@/lib/mockDraftMasterBoard";
import { buildDraftBoard, type DraftConfig } from "@/lib/draftRankings";
import type { Player } from "@/types/player";

const mockDraftConfig: DraftConfig = {
  leagueSize: 12,
  totalRosterSpots: 13,
  rosterSlots: {
    QB: 1,
    RB: 2,
    WR: 2,
    TE: 1,
    K: 1,
    BE: 5,
    IR: 0,
  },
};

const makePlayer = (overrides: Partial<Player>): Player => ({
  id: 1,
  name: "Existing Player",
  school: "Existing School",
  pos: "WR",
  conf: "N/A",
  rank: 1,
  boardRank: 1,
  adp: 1,
  posRank: 1,
  rostered: 0,
  status: "HEALTHY",
  projection: { fpts: 100 },
  history: [],
  analysis: "",
  ...overrides,
});

describe("mock draft master board fallback", () => {
  it("adds Jeremiah Smith when the backend player pool does not include him", () => {
    const missingPlayers = createMissingCfb27MockDraftPlayers([]);
    const jeremiah = missingPlayers.find((player) => player.name === "Jeremiah Smith");

    expect(jeremiah).toBeTruthy();
    expect(jeremiah?.school).toBe("Ohio State");
    expect(jeremiah?.pos).toBe("WR");
    expect(jeremiah?.id).toBeLessThan(0);
    expect(jeremiah?.boardRank).toBe(1);
  });

  it("does not duplicate CFB27 players already returned by the backend", () => {
    const existing = makePlayer({
      id: 42,
      name: "Jeremiah Smith",
      school: "Ohio State",
      pos: "WR",
    });

    const merged = mergeMockDraftMasterBoardPlayers([existing]);
    const jeremiahRows = merged.filter((player) => player.name === "Jeremiah Smith");

    expect(jeremiahRows).toHaveLength(1);
    expect(jeremiahRows[0].id).toBe(42);
  });

  it("hydrates existing CFB27 players with a usable mock projection and global board rank", () => {
    const existing = makePlayer({
      id: 17,
      name: "Dante Moore",
      school: "Oregon",
      pos: "QB",
      rank: 201,
      boardRank: 201,
      adp: 201,
      projection: { fpts: 0 },
    });

    const dante = mergeMockDraftMasterBoardPlayers([existing]).find((player) => player.id === 17);

    expect(dante?.rank).toBeLessThan(30);
    expect(dante?.boardRank).toBe(dante?.rank);
    expect(dante?.sheetProjectedSeasonPoints).toBeGreaterThan(0);
    expect(dante?.projection.fpts).toBeGreaterThan(0);
  });

  it("keeps real-draft enrichment scoped to persisted backend players", () => {
    const existing = makePlayer({
      id: 17,
      name: "Dante Moore",
      school: "Oregon",
      pos: "QB",
      projection: { fpts: 0 },
    });

    const enriched = enrichCfb27DraftPlayers([existing]);

    expect(enriched).toHaveLength(1);
    expect(enriched[0].id).toBe(17);
    expect(enriched[0].projection.fpts).toBeGreaterThan(0);
  });

  it("places top CFB27 quarterbacks in the early board instead of grouping them at the end", () => {
    const board = buildDraftBoard(mergeMockDraftMasterBoardPlayers([]), mockDraftConfig);
    const quarterbacks = board
      .filter((player) => player.pos === "QB")
      .sort((left, right) => left.masterDraftRank - right.masterDraftRank);
    const dante = quarterbacks.find((player) => player.name === "Dante Moore");
    const fifthQuarterback = quarterbacks[4];

    expect(dante?.masterDraftRank).toBeGreaterThanOrEqual(22);
    expect(dante?.masterDraftRank).toBeLessThanOrEqual(30);
    expect(fifthQuarterback?.masterDraftRank).toBeLessThan(80);
    expect(quarterbacks.slice(0, 5).map((player) => player.masterDraftRank)).not.toEqual(
      [201, 202, 203, 204, 205]
    );
  });
});
