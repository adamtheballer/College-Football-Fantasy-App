import { describe, expect, it } from "vitest";

import { buildDraftBoard, type DraftConfig } from "./draftRankings";
import type { Player } from "@/types/player";

const config: DraftConfig = {
  leagueSize: 12,
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

const makePlayer = (
  id: number,
  pos: string,
  fpts: number,
  options: Partial<Player> = {}
): Player => ({
  id,
  name: `${pos} Player ${id}`,
  school: "Georgia",
  pos,
  conf: "SEC",
  rank: id,
  adp: id,
  posRank: id,
  rostered: 0,
  status: "HEALTHY",
  projection: {
    fpts,
    passingYards: pos === "QB" ? fpts * 10 : 0,
    passingTds: 0,
    ints: 0,
    rushingYards: pos === "RB" ? fpts * 10 : 0,
    rushingTds: 0,
    receptions: pos === "WR" || pos === "TE" ? 4 : 0,
    receivingYards: pos === "WR" || pos === "TE" ? fpts * 10 : 0,
    receivingTds: 0,
    expectedPlays: fpts,
  },
  history: [],
  analysis: "",
  ...options,
});

describe("buildDraftBoard", () => {
  it("keeps RB/WR/TE projections monotonic by pre-draft board rank", () => {
    const players: Player[] = [
      ...Array.from({ length: 30 }, (_, index) => makePlayer(index + 1, "RB", 220 - index)),
      makePlayer(1001, "RB", 500, { name: "Late High Projection RB", adp: 300, posRank: 40 }),
      ...Array.from({ length: 30 }, (_, index) => makePlayer(2000 + index, "WR", 210 - index)),
      makePlayer(3001, "WR", 480, { name: "Late High Projection WR", adp: 320, posRank: 45 }),
      ...Array.from({ length: 30 }, (_, index) => makePlayer(4000 + index, "TE", 180 - index)),
      makePlayer(5001, "TE", 450, { name: "Late High Projection TE", adp: 350, posRank: 45 }),
      ...Array.from({ length: 20 }, (_, index) => makePlayer(6000 + index, "QB", 260 - index)),
      ...Array.from({ length: 20 }, (_, index) => makePlayer(7000 + index, "K", 100 - index)),
    ];

    const board = buildDraftBoard(players, config);

    for (const position of ["RB", "WR", "TE"]) {
      const positionPlayers = board
        .filter((player) => player.pos === position)
        .sort((left, right) => left.draftRank - right.draftRank);
      for (let index = 1; index < positionPlayers.length; index += 1) {
        expect(positionPlayers[index].projectedPoints).toBeLessThanOrEqual(
          positionPlayers[index - 1].projectedPoints
        );
      }
    }
  });

  it("keeps explicit source ranks as metadata while rendering dense master ranks", () => {
    const players: Player[] = [
      makePlayer(1, "RB", 100, { name: "Set Rank One", rank: 1, adp: 1 }),
      makePlayer(2, "QB", 500, { name: "Set Rank One Hundred", rank: 100, adp: 100 }),
      makePlayer(3, "TE", 450, { name: "Set Rank Two Eighty Seven", rank: 287, adp: 287 }),
    ];

    const board = buildDraftBoard(players, config);
    const playersByName = new Map(board.map((player) => [player.name, player]));

    expect(playersByName.get("Set Rank One")?.sourceBoardRank).toBe(1);
    expect(playersByName.get("Set Rank One Hundred")?.sourceBoardRank).toBe(100);
    expect(playersByName.get("Set Rank Two Eighty Seven")?.sourceBoardRank).toBe(287);

    expect([...board].sort((left, right) => left.masterDraftRank - right.masterDraftRank).map((player) => player.masterDraftRank)).toEqual([1, 2, 3]);
    expect([...board].sort((left, right) => left.draftRank - right.draftRank).map((player) => player.draftRank)).toEqual([1, 2, 3]);
  });

  it("applies only a small WR board penalty outside the top fifteen", () => {
    const players: Player[] = Array.from({ length: 20 }, (_, index) => {
      const rank = index + 1;
      const pos = rank === 16 ? "WR" : rank === 17 ? "RB" : "QB";
      return makePlayer(rank, pos, 300 - rank, {
        name: `Rank ${rank}`,
        rank,
        adp: rank,
      });
    });

    const board = buildDraftBoard(players, config);
    const byName = new Map(board.map((player) => [player.name, player]));

    for (let rank = 1; rank <= 15; rank += 1) {
      expect(byName.get(`Rank ${rank}`)?.masterDraftRank).toBe(rank);
    }

    expect(byName.get("Rank 16")?.pos).toBe("WR");
    expect(byName.get("Rank 16")?.masterDraftRank).toBeGreaterThan(16);
    expect(byName.get("Rank 16")?.masterDraftRank).toBeLessThanOrEqual(18);
    expect(byName.get("Rank 16")?.projectedPoints).toBeGreaterThan(0);
  });

  it("forces early-ranked low-projection backup QBs to the end of the draft board", () => {
    const players: Player[] = [
      makePlayer(1, "RB", 320, { name: "Elite RB", rank: 1, adp: 1 }),
      makePlayer(2, "QB", 310, { name: "Starting QB", rank: 2, adp: 2 }),
      makePlayer(3, "QB", 3.3, { name: "Deuce Knight Type Backup", rank: 3, adp: 3 }),
      makePlayer(4, "WR", 290, { name: "Elite WR", rank: 4, adp: 4 }),
      makePlayer(5, "TE", 260, { name: "Elite TE", rank: 5, adp: 5 }),
      makePlayer(6, "QB", 16.6, { name: "Beau Allen Type Backup", rank: 6, adp: 6 }),
      ...Array.from({ length: 18 }, (_, index) =>
        makePlayer(100 + index, index % 2 === 0 ? "RB" : "WR", 240 - index, {
          name: `Draftable Skill ${index + 1}`,
          rank: 20 + index,
          adp: 20 + index,
        })
      ),
    ];

    const board = buildDraftBoard(players, config);
    const byName = new Map(board.map((player) => [player.name, player]));
    const deuceType = byName.get("Deuce Knight Type Backup");
    const beauType = byName.get("Beau Allen Type Backup");
    const lastRanks = [...board].slice(-2).map((player) => player.name);

    expect(deuceType?.sourceBoardRank).toBe(3);
    expect(beauType?.sourceBoardRank).toBe(6);
    expect(lastRanks).toEqual(["Beau Allen Type Backup", "Deuce Knight Type Backup"]);
    expect(deuceType?.masterDraftRank).toBe(board.length);
    expect(beauType?.masterDraftRank).toBe(board.length - 1);
    expect(byName.get("Starting QB")?.masterDraftRank).toBeLessThan(
      beauType?.masterDraftRank ?? 0
    );
  });

  it("promotes high-projection starting QBs when stale source rank buries them", () => {
    const players: Player[] = [
      makePlayer(1, "RB", 340, { name: "Elite RB", rank: 1, adp: 1 }),
      makePlayer(2, "QB", 325, { name: "Top QB", rank: 2, adp: 2 }),
      ...Array.from({ length: 34 }, (_, index) => {
        const rank = index + 3;
        return makePlayer(200 + index, index % 2 === 0 ? "RB" : "WR", 260 - index, {
          name: `Normal Draftable ${rank}`,
          rank,
          adp: rank,
        });
      }),
      makePlayer(999, "QB", 316, {
        name: "LaNorris Sellers Type Starter",
        rank: 120,
        adp: 120,
        posRank: 4,
      }),
      makePlayer(1000, "QB", 3.3, {
        name: "Buried Backup QB",
        rank: 4,
        adp: 4,
      }),
    ];

    const board = buildDraftBoard(players, config);
    const byName = new Map(board.map((player) => [player.name, player]));
    const sellersType = byName.get("LaNorris Sellers Type Starter");
    const backup = byName.get("Buried Backup QB");

    expect(sellersType?.sourceBoardRank).toBe(120);
    expect(sellersType?.projectedPoints).toBe(316);
    expect(sellersType?.masterDraftRank).toBeLessThanOrEqual(20);
    expect(backup?.masterDraftRank).toBe(board.length);
    expect(sellersType?.masterDraftRank).toBeLessThan(backup?.masterDraftRank ?? 0);
  });

  it("uses sheet season projections for the draft board when present", () => {
    const board = buildDraftBoard(
      [
        makePlayer(1, "RB", 10, {
          name: "Sheet Projection RB",
          rank: 1,
          adp: 1,
          sheetProjectedSeasonPoints: 347.4,
        }),
      ],
      config
    );

    expect(board[0].draftRank).toBe(1);
    expect(board[0].projectedPoints).toBe(347.4);
  });

  it("blends provided game overall ratings into otherwise similar player rankings", () => {
    const board = buildDraftBoard(
      [
        makePlayer(1, "WR", 210, {
          name: "Jeremiah Smith",
          school: "Ohio State",
          rank: 20,
          adp: 20,
          posRank: 10,
        }),
        makePlayer(2, "WR", 210, {
          name: "DeAndre Moore Jr.",
          school: "Colorado",
          rank: 20,
          adp: 20,
          posRank: 10,
        }),
        ...Array.from({ length: 18 }, (_, index) =>
          makePlayer(100 + index, index % 2 === 0 ? "RB" : "QB", 205 - index, {
            name: `Control Player ${index + 1}`,
            rank: 30 + index,
            adp: 30 + index,
          })
        ),
      ],
      config
    );

    const byName = new Map(board.map((player) => [player.name, player]));
    const highRated = byName.get("Jeremiah Smith");
    const lowerRated = byName.get("DeAndre Moore Jr.");

    expect(highRated?.cfb27Overall).toBe(99);
    expect(lowerRated?.cfb27Overall).toBe(86);
    expect(highRated?.finalDraftScore ?? 0).toBeGreaterThan(lowerRated?.finalDraftScore ?? 0);
    expect(highRated?.masterDraftRank ?? 0).toBeLessThan(lowerRated?.masterDraftRank ?? 0);
  });
});
