import type { DraftPlayer } from "@/lib/draftRankings";
import {
  assignBestRosterSlotForPosition,
  filterDraftablePlayers,
  getLegalPositionsForRoster,
  type PlayerPosition,
  type RosterPlayer,
  type RosterSlotLimits,
} from "@/lib/rosterLegality";

export const MOCK_TEAM_COUNT = 12;
export const MOCK_ROUNDS = 13;
export const MOCK_TOTAL_PICKS = MOCK_TEAM_COUNT * MOCK_ROUNDS;
export const MOCK_USER_TEAM_ID = 6;
export const MOCK_INTERMISSION_SECONDS = 5;
export const MOCK_BOT_PICK_DELAY_SECONDS = 2;
export const MOCK_PICK_TIMER_SECONDS = 30;

export type MockDraftTeam = {
  id: number;
  name: string;
  managerType: "user" | "bot";
};

export type MockDraftPick = {
  overallPick: number;
  round: number;
  roundPick: number;
  teamId: number;
  teamName: string;
  playerId: number;
  playerName: string;
  position: string;
  school: string;
  projectedPoints: number;
  draftRank: number;
  masterDraftRank: number;
  assignedSlot?: string;
  pickedBy: "user" | "bot" | "auto";
  madeAt: number;
};

export type SinglePlayerMockDraftStatus = "intermission" | "live" | "complete";

export type SinglePlayerMockDraftState = {
  id: string;
  status: SinglePlayerMockDraftStatus;
  createdAt: number;
  intermissionEndsAt: number;
  currentPick: number;
  pickStartedAt: number | null;
  pickExpiresAt: number | null;
  userTeamId: number;
  teams: MockDraftTeam[];
  picks: MockDraftPick[];
  queuedPlayerIds: number[];
};

export type MockRosterSlot = {
  label: string;
  allowedPositions: string[];
  player?: MockDraftPick;
};

export type MockDraftInitialStateResolution = {
  state: SinglePlayerMockDraftState;
  shouldClearStoredDraft: boolean;
  shouldReplaceUrl: boolean;
};

export type CarouselScrollInput = {
  overallPick: number;
  cardOffsetLeft: number;
  cardWidth: number;
  containerWidth: number;
};

const STARTER_SLOTS: Array<{ label: string; allowedPositions: string[] }> = [
  { label: "QB", allowedPositions: ["QB"] },
  { label: "RB 1", allowedPositions: ["RB"] },
  { label: "RB 2", allowedPositions: ["RB"] },
  { label: "WR 1", allowedPositions: ["WR"] },
  { label: "WR 2", allowedPositions: ["WR"] },
  { label: "TE", allowedPositions: ["TE"] },
  { label: "FLEX", allowedPositions: ["RB", "WR", "TE"] },
  { label: "K", allowedPositions: ["K"] },
];

const BENCH_SLOTS = 5;
export const MOCK_ROSTER_SLOT_LIMITS: RosterSlotLimits = {
  QB: 1,
  RB: 2,
  WR: 2,
  TE: 1,
  FLEX: 1,
  K: 1,
  BENCH: BENCH_SLOTS,
};

export const createMockTeams = (): MockDraftTeam[] =>
  Array.from({ length: MOCK_TEAM_COUNT }, (_, index) => {
    const id = index + 1;
    return {
      id,
      name: id === MOCK_USER_TEAM_ID ? "Your Team" : `Bot Team ${id}`,
      managerType: id === MOCK_USER_TEAM_ID ? "user" : "bot",
    };
  });

export const createSinglePlayerMockDraft = (now = Date.now()): SinglePlayerMockDraftState => ({
  id: `local-${now}`,
  status: "intermission",
  createdAt: now,
  intermissionEndsAt: now + MOCK_INTERMISSION_SECONDS * 1000,
  currentPick: 1,
  pickStartedAt: null,
  pickExpiresAt: null,
  userTeamId: MOCK_USER_TEAM_ID,
  teams: createMockTeams(),
  picks: [],
  queuedPlayerIds: [],
});

export const shouldStartNewSinglePlayerMockDraft = (search = "") => {
  const params = new URLSearchParams(search.startsWith("?") ? search : `?${search}`);
  return params.get("new") === "1";
};

export const resolveInitialSinglePlayerMockDraftState = ({
  search = "",
  storedState,
  now = Date.now(),
}: {
  search?: string;
  storedState?: SinglePlayerMockDraftState | null;
  now?: number;
}): MockDraftInitialStateResolution => {
  if (shouldStartNewSinglePlayerMockDraft(search)) {
    return {
      state: createSinglePlayerMockDraft(now),
      shouldClearStoredDraft: true,
      shouldReplaceUrl: true,
    };
  }

  return {
    state: storedState ?? createSinglePlayerMockDraft(now),
    shouldClearStoredDraft: false,
    shouldReplaceUrl: false,
  };
};

export const getRoundNumber = (overallPick: number) =>
  Math.floor((overallPick - 1) / MOCK_TEAM_COUNT) + 1;

export const getRoundPick = (overallPick: number) =>
  ((overallPick - 1) % MOCK_TEAM_COUNT) + 1;

export const getTeamIdForPick = (overallPick: number) => {
  const round = getRoundNumber(overallPick);
  const roundPick = getRoundPick(overallPick);
  return round % 2 === 1 ? roundPick : MOCK_TEAM_COUNT - roundPick + 1;
};

export const getCurrentTeam = (state: SinglePlayerMockDraftState) =>
  state.teams.find((team) => team.id === getTeamIdForPick(state.currentPick));

export const isUserOnClock = (state: SinglePlayerMockDraftState) =>
  state.status === "live" && getTeamIdForPick(state.currentPick) === state.userTeamId;

export const isPickTimerDanger = (
  state: SinglePlayerMockDraftState,
  secondsRemaining: number
) => state.status === "live" && secondsRemaining > 0 && secondsRemaining <= 10;

export const getCenteredDraftCarouselScrollLeft = ({
  overallPick,
  cardOffsetLeft,
  cardWidth,
  containerWidth,
}: CarouselScrollInput) => {
  if (overallPick <= 3) {
    return 0;
  }
  return Math.max(0, cardOffsetLeft - containerWidth / 2 + cardWidth / 2);
};

const draftedPlayerIds = (state: SinglePlayerMockDraftState) =>
  new Set(state.picks.map((pick) => pick.playerId));

const getPlayerBoardRank = (player: DraftPlayer) => player.masterDraftRank ?? player.draftRank;

const compareDraftBoardPlayers = (left: DraftPlayer, right: DraftPlayer) => {
  const leftRank = getPlayerBoardRank(left);
  const rightRank = getPlayerBoardRank(right);
  if (leftRank !== rightRank) {
    return leftRank - rightRank;
  }
  if (left.projectedPoints !== right.projectedPoints) {
    return right.projectedPoints - left.projectedPoints;
  }
  return left.name.localeCompare(right.name);
};

export const getAvailablePlayers = (
  board: DraftPlayer[],
  state: SinglePlayerMockDraftState
) => {
  const drafted = draftedPlayerIds(state);
  return board
    .filter((player) => !drafted.has(player.id))
    .sort(compareDraftBoardPlayers);
};

export const getMockRosterPlayers = (
  state: SinglePlayerMockDraftState,
  teamId = getTeamIdForPick(state.currentPick)
): RosterPlayer[] =>
  state.picks
    .filter((pick) => pick.teamId === teamId)
    .map((pick) => ({
      id: pick.playerId,
      position: pick.position,
      assignedSlot: pick.assignedSlot,
    }));

export const getLegalMockPositionsForTeam = (
  state: SinglePlayerMockDraftState,
  teamId = getTeamIdForPick(state.currentPick)
): PlayerPosition[] =>
  getLegalPositionsForRoster(getMockRosterPlayers(state, teamId), MOCK_ROSTER_SLOT_LIMITS);

export const getDraftablePlayersForTeam = (
  board: DraftPlayer[],
  state: SinglePlayerMockDraftState,
  teamId = getTeamIdForPick(state.currentPick)
) =>
  filterDraftablePlayers(
    board,
    getMockRosterPlayers(state, teamId),
    MOCK_ROSTER_SLOT_LIMITS,
    draftedPlayerIds(state)
  ).sort(compareDraftBoardPlayers);

const getBestAvailablePlayer = (
  board: DraftPlayer[],
  state: SinglePlayerMockDraftState,
  preferredPlayerIds: number[] = []
) => {
  const available = getDraftablePlayersForTeam(board, state);
  const availableById = new Map(available.map((player) => [player.id, player]));
  for (const playerId of preferredPlayerIds) {
    const queuedPlayer = availableById.get(playerId);
    if (queuedPlayer) return queuedPlayer;
  }
  return available[0];
};

const createPick = (
  state: SinglePlayerMockDraftState,
  player: DraftPlayer,
  assignedSlot: string,
  pickedBy: MockDraftPick["pickedBy"],
  now: number
): MockDraftPick => {
  const teamId = getTeamIdForPick(state.currentPick);
  const team = state.teams.find((row) => row.id === teamId);
  return {
    overallPick: state.currentPick,
    round: getRoundNumber(state.currentPick),
    roundPick: getRoundPick(state.currentPick),
    teamId,
    teamName: team?.name ?? `Team ${teamId}`,
    playerId: player.id,
    playerName: player.name,
    position: player.pos,
    school: player.school,
    projectedPoints: player.projectedPoints,
    draftRank: getPlayerBoardRank(player),
    masterDraftRank: getPlayerBoardRank(player),
    assignedSlot,
    pickedBy,
    madeAt: now,
  };
};

const startCurrentPickTimer = (
  state: SinglePlayerMockDraftState,
  now: number
): SinglePlayerMockDraftState => ({
  ...state,
  pickStartedAt: now,
  pickExpiresAt: now + MOCK_PICK_TIMER_SECONDS * 1000,
});

const appendPick = (
  state: SinglePlayerMockDraftState,
  pick: MockDraftPick,
  now: number
): SinglePlayerMockDraftState => {
  const nextPick = state.currentPick + 1;
  if (nextPick > MOCK_TOTAL_PICKS) {
    return {
      ...state,
      status: "complete",
      currentPick: MOCK_TOTAL_PICKS,
      pickStartedAt: null,
      pickExpiresAt: null,
      picks: [...state.picks, pick],
      queuedPlayerIds: state.queuedPlayerIds.filter((id) => id !== pick.playerId),
    };
  }
  return startCurrentPickTimer(
    {
      ...state,
      currentPick: nextPick,
      picks: [...state.picks, pick],
      queuedPlayerIds: state.queuedPlayerIds.filter((id) => id !== pick.playerId),
    },
    now
  );
};

export const makeUserMockPick = (
  state: SinglePlayerMockDraftState,
  board: DraftPlayer[],
  playerId: number,
  now = Date.now()
) => {
  if (!isUserOnClock(state)) {
    throw new Error("It is not your turn.");
  }
  const player = getDraftablePlayersForTeam(board, state).find((row) => row.id === playerId);
  if (!player) {
    const alreadyDrafted = draftedPlayerIds(state).has(playerId);
    throw new Error(
      alreadyDrafted
        ? "That player has already been drafted."
        : "You cannot draft this player because your roster has no open slot for this position."
    );
  }
  const assignedSlot = assignBestRosterSlotForPosition(
    player.pos,
    getMockRosterPlayers(state),
    MOCK_ROSTER_SLOT_LIMITS
  );
  if (!assignedSlot) {
    throw new Error("You cannot draft this player because your roster has no open slot for this position.");
  }
  return appendPick(state, createPick(state, player, assignedSlot, "user", now), now);
};

export const toggleQueuedMockPlayer = (
  state: SinglePlayerMockDraftState,
  playerId: number
): SinglePlayerMockDraftState => {
  const exists = state.queuedPlayerIds.includes(playerId);
  return {
    ...state,
    queuedPlayerIds: exists
      ? state.queuedPlayerIds.filter((id) => id !== playerId)
      : [...state.queuedPlayerIds, playerId],
  };
};

export const advanceSinglePlayerMockDraft = (
  state: SinglePlayerMockDraftState,
  board: DraftPlayer[],
  now = Date.now()
): SinglePlayerMockDraftState => {
  let nextState = { ...state };

  if (nextState.status === "complete") {
    return nextState;
  }

  if (nextState.status === "intermission") {
    if (now < nextState.intermissionEndsAt) {
      return nextState;
    }
    nextState = startCurrentPickTimer({ ...nextState, status: "live" }, now);
  }

  let guard = 0;
  while (nextState.status === "live" && guard < MOCK_TOTAL_PICKS) {
    guard += 1;
    const currentTeam = getCurrentTeam(nextState);
    const isBotTurn = currentTeam?.managerType === "bot";
    const pickStartedAt = nextState.pickStartedAt ?? now;
    const pickExpired = Boolean(nextState.pickExpiresAt && now >= nextState.pickExpiresAt);
    const botReady = isBotTurn && now - pickStartedAt >= MOCK_BOT_PICK_DELAY_SECONDS * 1000;
    const userAutoPickReady = !isBotTurn && pickExpired;

    if (!botReady && !userAutoPickReady) {
      return nextState;
    }

    const player = getBestAvailablePlayer(
      board,
      nextState,
      userAutoPickReady ? nextState.queuedPlayerIds : []
    );
    if (!player) {
      return {
        ...nextState,
        status: "complete",
        currentPick: MOCK_TOTAL_PICKS,
        pickStartedAt: null,
        pickExpiresAt: null,
      };
    }

    const assignedSlot = assignBestRosterSlotForPosition(
      player.pos,
      getMockRosterPlayers(nextState),
      MOCK_ROSTER_SLOT_LIMITS
    );
    if (!assignedSlot) {
      return nextState;
    }

    nextState = appendPick(
      nextState,
      createPick(nextState, player, assignedSlot, isBotTurn ? "bot" : "auto", now),
      now
    );
  }

  return nextState;
};

export const getSecondsRemaining = (
  state: SinglePlayerMockDraftState,
  now = Date.now()
) => {
  if (state.status === "intermission") {
    return Math.max(0, Math.ceil((state.intermissionEndsAt - now) / 1000));
  }
  if (state.status !== "live" || !state.pickExpiresAt) {
    return 0;
  }
  return Math.max(0, Math.ceil((state.pickExpiresAt - now) / 1000));
};

export const buildMockRoster = (
  state: SinglePlayerMockDraftState,
  teamId = state.userTeamId
): MockRosterSlot[] => {
  const slots: MockRosterSlot[] = [
    ...STARTER_SLOTS.map((slot) => ({ ...slot })),
    ...Array.from({ length: BENCH_SLOTS }, (_, index) => ({
      label: `BENCH ${index + 1}`,
      allowedPositions: ["QB", "RB", "WR", "TE", "K"],
    })),
  ];

  const picks = state.picks.filter((pick) => pick.teamId === teamId);
  for (const pick of picks) {
    const assignedSlot = pick.assignedSlot;
    if (assignedSlot) {
      const exactSlot = slots.find((slot) => !slot.player && slot.label === assignedSlot);
      if (exactSlot) {
        exactSlot.player = pick;
        continue;
      }
      if (assignedSlot === "BENCH") {
        const exactBench = slots.find((slot) => !slot.player && slot.label.startsWith("BENCH"));
        if (exactBench) {
          exactBench.player = pick;
          continue;
        }
      }
    }

    const openStarter = slots.find(
      (slot) => !slot.player && slot.allowedPositions.includes(pick.position)
    );
    if (openStarter) {
      openStarter.player = pick;
      continue;
    }
    const openBench = slots.find((slot) => !slot.player && slot.label.startsWith("BENCH"));
    if (openBench) {
      openBench.player = pick;
    }
  }

  return slots;
};
