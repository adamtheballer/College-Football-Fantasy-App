import { describe, expect, it } from "vitest";

import {
  createMissingCfb27MockDraftPlayers,
  mergeMockDraftMasterBoardPlayers,
} from "@/lib/mockDraftMasterBoard";
import type { Player } from "@/types/player";

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
});
