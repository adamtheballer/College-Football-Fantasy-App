import { describe, expect, it } from "vitest";

import {
  advanceSinglePlayerMockDraft,
  buildMockRoster,
  createSinglePlayerMockDraft,
  getCurrentTeam,
  getAvailablePlayers,
  getCenteredDraftCarouselScrollLeft,
  getDraftablePlayersForTeam,
  getLegalMockPositionsForTeam,
  getTeamIdForPick,
  isPickTimerDanger,
  isUserOnClock,
  makeUserMockPick,
  MOCK_BOT_PICK_DELAY_SECONDS,
  MOCK_INTERMISSION_SECONDS,
  MOCK_PICK_TIMER_SECONDS,
  MOCK_TOTAL_PICKS,
  MOCK_USER_TEAM_ID,
  resolveInitialSinglePlayerMockDraftState,
} from "./singlePlayerMockDraft";
import type { DraftPlayer } from "./draftRankings";
import type { MockDraftPick, SinglePlayerMockDraftState } from "./singlePlayerMockDraft";

const player = (id: number, pos = "RB"): DraftPlayer => ({
  id,
  name: `Player ${id}`,
  school: `School ${id}`,
  pos,
  conf: "SEC",
  rank: id,
  adp: id,
  posRank: id,
  rostered: 0,
  status: "HEALTHY",
  projection: { fpts: 250 - id },
  history: [],
  analysis: "",
  draftRank: id,
  masterDraftRank: id,
  sourceBoardRank: id,
  adpRank: id,
  adpEstimate: id,
  projectedPoints: 250 - id,
  tier: 1,
  tprScore: 250 - id,
  marScore: 250 - id,
  finalDraftScore: 250 - id,
  cfb27Overall: null,
  cfb27TalentScore: 0.5,
});

const board = Array.from({ length: 180 }, (_, index) =>
  player(index + 1, ["QB", "RB", "WR", "TE", "K"][index % 5])
);

const pick = (
  id: number,
  position: string,
  teamId: number,
  assignedSlot: string,
  overallPick = id
): MockDraftPick => ({
  overallPick,
  round: 1,
  roundPick: overallPick,
  teamId,
  teamName: `Team ${teamId}`,
  playerId: id,
  playerName: `${position} Pick ${id}`,
  position,
  school: `School ${id}`,
  projectedPoints: 100,
  draftRank: id,
  masterDraftRank: id,
  assignedSlot,
  pickedBy: "bot",
  madeAt: 1_000,
});

const fillTeamExceptK = (
  state: SinglePlayerMockDraftState,
  teamId: number
): SinglePlayerMockDraftState => ({
  ...state,
  picks: [
    pick(9001, "QB", teamId, "QB"),
    pick(9002, "RB", teamId, "RB"),
    pick(9003, "RB", teamId, "RB"),
    pick(9004, "WR", teamId, "WR"),
    pick(9005, "WR", teamId, "WR"),
    pick(9006, "TE", teamId, "TE"),
    pick(9007, "RB", teamId, "FLEX"),
    pick(9008, "QB", teamId, "BENCH"),
    pick(9009, "RB", teamId, "BENCH"),
    pick(9010, "WR", teamId, "BENCH"),
    pick(9011, "TE", teamId, "BENCH"),
    pick(9012, "WR", teamId, "BENCH"),
  ],
});

describe("single-player mock draft engine", () => {
  it("starts a fresh mock when new=1 is present and clears stored state", () => {
    const stored = {
      ...createSinglePlayerMockDraft(1_000),
      status: "complete" as const,
      currentPick: MOCK_TOTAL_PICKS,
    };

    const resolved = resolveInitialSinglePlayerMockDraftState({
      search: "?new=1",
      storedState: stored,
      now: 5_000,
    });

    expect(resolved.shouldClearStoredDraft).toBe(true);
    expect(resolved.shouldReplaceUrl).toBe(true);
    expect(resolved.state.id).toBe("local-5000");
    expect(resolved.state.status).toBe("intermission");
    expect(resolved.state.picks).toHaveLength(0);
  });

  it("resumes an existing mock when new=1 is absent", () => {
    const stored = createSinglePlayerMockDraft(1_000);
    const resolved = resolveInitialSinglePlayerMockDraftState({
      search: "",
      storedState: stored,
      now: 5_000,
    });

    expect(resolved.shouldClearStoredDraft).toBe(false);
    expect(resolved.shouldReplaceUrl).toBe(false);
    expect(resolved.state).toBe(stored);
  });

  it("starts after intermission and bot auto-picks first overall", () => {
    const start = 1_000;
    const initial = createSinglePlayerMockDraft(start);

    const live = advanceSinglePlayerMockDraft(
      initial,
      board,
      start + MOCK_INTERMISSION_SECONDS * 1000
    );
    expect(live.status).toBe("live");
    expect(live.picks).toHaveLength(0);
    expect(getCurrentTeam(live)?.managerType).toBe("bot");

    const afterBot = advanceSinglePlayerMockDraft(
      live,
      board,
      start + MOCK_INTERMISSION_SECONDS * 1000 + MOCK_BOT_PICK_DELAY_SECONDS * 1000
    );
    expect(afterBot.picks).toHaveLength(1);
    expect(afterBot.picks[0].pickedBy).toBe("bot");
    expect(afterBot.picks[0].playerId).toBe(1);
    expect(afterBot.picks[0].draftRank).toBe(1);
    expect(afterBot.currentPick).toBe(2);
  });

  it("bot auto-picks the lowest true board rank even when input order is scrambled", () => {
    const start = 1_000;
    const scrambledBoard = [player(12), player(3), player(1), player(8), player(2)].map(
      (row) =>
        row.id === 12
          ? { ...row, masterDraftRank: 99, draftRank: 99 }
          : row
    );
    const initial = createSinglePlayerMockDraft(start);
    const live = advanceSinglePlayerMockDraft(
      initial,
      scrambledBoard,
      start + MOCK_INTERMISSION_SECONDS * 1000
    );

    const afterBot = advanceSinglePlayerMockDraft(
      live,
      scrambledBoard,
      start + MOCK_INTERMISSION_SECONDS * 1000 + MOCK_BOT_PICK_DELAY_SECONDS * 1000
    );

    expect(afterBot.picks).toHaveLength(1);
    expect(afterBot.picks[0].playerId).toBe(1);
    expect(afterBot.picks[0].draftRank).toBe(1);
  });

  it("keeps master board ranks stable after picks and filters", () => {
    const start = 1_000;
    const state = createSinglePlayerMockDraft(start);
    const live = advanceSinglePlayerMockDraft(
      state,
      board,
      start + MOCK_INTERMISSION_SECONDS * 1000
    );
    const afterBot = advanceSinglePlayerMockDraft(
      live,
      board,
      start + MOCK_INTERMISSION_SECONDS * 1000 + MOCK_BOT_PICK_DELAY_SECONDS * 1000
    );

    const available = getAvailablePlayers(board, afterBot);
    expect(available[0].masterDraftRank).toBe(2);
    expect(available[0].draftRank).toBe(2);

    const tightEnds = available.filter((row) => row.pos === "TE");
    expect(tightEnds[0].masterDraftRank).not.toBe(1);
    expect(tightEnds[0].masterDraftRank).toBeGreaterThan(1);
  });

  it("centers carousel picks from pick four onward and keeps early picks at start", () => {
    expect(
      getCenteredDraftCarouselScrollLeft({
        overallPick: 3,
        cardOffsetLeft: 400,
        cardWidth: 180,
        containerWidth: 600,
      })
    ).toBe(0);

    expect(
      getCenteredDraftCarouselScrollLeft({
        overallPick: 4,
        cardOffsetLeft: 720,
        cardWidth: 180,
        containerWidth: 600,
      })
    ).toBe(510);
  });

  it("only marks the timer dangerous in the last ten seconds of live picks", () => {
    const start = 1_000;
    const live = {
      ...createSinglePlayerMockDraft(start),
      status: "live" as const,
      pickStartedAt: start,
      pickExpiresAt: start + MOCK_PICK_TIMER_SECONDS * 1000,
    };

    expect(isPickTimerDanger(live, 11)).toBe(false);
    expect(isPickTimerDanger(live, 10)).toBe(true);
    expect(isPickTimerDanger(live, 1)).toBe(true);
    expect(isPickTimerDanger({ ...live, status: "intermission" }, 5)).toBe(false);
    expect(isPickTimerDanger({ ...live, status: "complete" }, 5)).toBe(false);
  });

  it("only allows user picks on the user team turn", () => {
    const start = 1_000;
    const initial = createSinglePlayerMockDraft(start);
    const live = advanceSinglePlayerMockDraft(
      initial,
      board,
      start + MOCK_INTERMISSION_SECONDS * 1000
    );

    expect(() => makeUserMockPick(live, board, 1, start)).toThrow("It is not your turn.");

    let state = live;
    let now = start + MOCK_INTERMISSION_SECONDS * 1000;
    while (!isUserOnClock(state)) {
      now += MOCK_BOT_PICK_DELAY_SECONDS * 1000;
      state = advanceSinglePlayerMockDraft(state, board, now);
    }

    expect(getTeamIdForPick(state.currentPick)).toBe(MOCK_USER_TEAM_ID);
    const picked = makeUserMockPick(state, board, board[state.picks.length].id, now + 100);
    expect(picked.picks[picked.picks.length - 1]?.pickedBy).toBe("user");
  });

  it("can complete a full 12-team by 13-round mock without duplicate players", () => {
    const start = 1_000;
    let state = createSinglePlayerMockDraft(start);
    let now = start + MOCK_INTERMISSION_SECONDS * 1000;
    state = advanceSinglePlayerMockDraft(state, board, now);

    while (state.status !== "complete") {
      if (isUserOnClock(state)) {
        const bestAvailable = getDraftablePlayersForTeam(board, state)[0];
        expect(bestAvailable).toBeDefined();
        state = makeUserMockPick(state, board, bestAvailable!.id, now);
      } else {
        now += MOCK_BOT_PICK_DELAY_SECONDS * 1000;
        state = advanceSinglePlayerMockDraft(state, board, now);
      }
    }

    expect(state.picks).toHaveLength(MOCK_TOTAL_PICKS);
    expect(new Set(state.picks.map((pick) => pick.playerId)).size).toBe(MOCK_TOTAL_PICKS);
    expect(buildMockRoster(state).every((slot) => Boolean(slot.player))).toBe(true);
    expect(buildMockRoster(state).some((slot) => slot.label === "K" && slot.player?.position === "K")).toBe(true);
  });

  it("only exposes kickers and rejects illegal user picks when the on-clock roster only has K open", () => {
    const start = 1_000;
    const base = {
      ...createSinglePlayerMockDraft(start),
      status: "live" as const,
      currentPick: MOCK_USER_TEAM_ID,
      pickStartedAt: start,
      pickExpiresAt: start + MOCK_PICK_TIMER_SECONDS * 1000,
    };
    const state = fillTeamExceptK(base, MOCK_USER_TEAM_ID);
    const kOnlyBoard = [
      player(100, "QB"),
      player(101, "RB"),
      player(102, "WR"),
      player(103, "TE"),
      player(104, "K"),
    ];

    expect(getLegalMockPositionsForTeam(state, MOCK_USER_TEAM_ID)).toEqual(["K"]);
    expect(getDraftablePlayersForTeam(kOnlyBoard, state).map((row) => row.pos)).toEqual(["K"]);
    expect(() => makeUserMockPick(state, kOnlyBoard, 100, start)).toThrow(
      "You cannot draft this player because your roster has no open slot for this position."
    );

    const afterKicker = makeUserMockPick(state, kOnlyBoard, 104, start);
    const lastPick = afterKicker.picks[afterKicker.picks.length - 1];
    expect(lastPick.position).toBe("K");
    expect(lastPick.assignedSlot).toBe("K");
  });

  it("bot auto-pick selects a kicker when that bot only has K open", () => {
    const start = 1_000;
    const base = {
      ...createSinglePlayerMockDraft(start),
      status: "live" as const,
      currentPick: 1,
      pickStartedAt: start,
      pickExpiresAt: start + MOCK_PICK_TIMER_SECONDS * 1000,
    };
    const state = fillTeamExceptK(base, 1);
    const kOnlyBoard = [
      player(100, "QB"),
      player(101, "RB"),
      player(102, "WR"),
      player(103, "TE"),
      player(104, "K"),
    ];

    const afterBot = advanceSinglePlayerMockDraft(
      state,
      kOnlyBoard,
      start + MOCK_BOT_PICK_DELAY_SECONDS * 1000
    );
    const lastPick = afterBot.picks[afterBot.picks.length - 1];
    expect(lastPick.position).toBe("K");
    expect(lastPick.assignedSlot).toBe("K");
  });
});
