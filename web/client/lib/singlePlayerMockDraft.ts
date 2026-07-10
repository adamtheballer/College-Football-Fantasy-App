import { getDraftPlayerIdentityKey, type DraftPlayer } from "@/lib/draftRankings";
import {
  assignBestRosterSlotForPosition,
  filterDraftablePlayers,
  getLegalPositionsForRoster,
  type PlayerPosition,
  type RosterPlayer,
  type RosterSlotLimits,
} from "@/lib/rosterLegality";
import type { Player } from "@/types/player";

export const MOCK_TEAM_COUNT = 12;
export const MOCK_USER_TEAM_ID = 6;
export const MOCK_INTERMISSION_SECONDS = 5;
export const MOCK_BOT_PICK_DELAY_SECONDS = 2;
export const MOCK_PICK_TIMER_SECONDS = 30;

export type MockDraftSettings = {
  leagueSize: number;
  rounds: number;
  pickTimerSeconds: number;
};

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
  settings?: MockDraftSettings;
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

export const MOCK_ROUNDS = Object.values(MOCK_ROSTER_SLOT_LIMITS).reduce(
  (total, limit) => total + limit,
  0
);
export const MOCK_TOTAL_PICKS = MOCK_TEAM_COUNT * MOCK_ROUNDS;

export const DEFAULT_MOCK_DRAFT_SETTINGS: MockDraftSettings = {
  leagueSize: MOCK_TEAM_COUNT,
  rounds: MOCK_ROUNDS,
  pickTimerSeconds: MOCK_PICK_TIMER_SECONDS,
};

const LOCAL_MOCK_POSITION_COUNTS: Record<PlayerPosition, number> = {
  QB: 42,
  RB: 70,
  WR: 82,
  TE: 40,
  K: 30,
};

const LOCAL_MOCK_POSITION_BASE_PROJECTION: Record<PlayerPosition, number> = {
  QB: 330,
  RB: 315,
  WR: 305,
  TE: 245,
  K: 155,
};

export const createLocalMockDraftPlayerPool = (): Player[] => {
  const rows: Player[] = [];
  let id = 900_001;
  let rank = 1;

  for (const position of ["QB", "RB", "WR", "TE", "K"] as PlayerPosition[]) {
    const count = LOCAL_MOCK_POSITION_COUNTS[position];
    const baseProjection = LOCAL_MOCK_POSITION_BASE_PROJECTION[position];
    for (let index = 0; index < count; index += 1) {
      const positionRank = index + 1;
      const projectedPoints = Math.max(
        position === "K" ? 70 : 35,
        baseProjection - index * (position === "K" ? 2.1 : 3.2)
      );
      rows.push({
        id,
        name: `Mock ${position} ${String(positionRank).padStart(2, "0")}`,
        school: `Mock ${position} State`,
        pos: position,
        conf: "MOCK",
        rank,
        boardRank: rank,
        adp: rank,
        posRank: positionRank,
        rostered: 0,
        status: "HEALTHY",
        projection: {
          fpts: Number(projectedPoints.toFixed(1)),
          passingYards: position === "QB" ? Math.round(projectedPoints * 9) : 0,
          passingTds: position === "QB" ? Math.round(projectedPoints / 16) : 0,
          ints: position === "QB" ? Math.max(0, Math.round(positionRank / 6)) : 0,
          rushingYards: position === "QB" || position === "RB" ? Math.round(projectedPoints * 2.2) : 0,
          rushingTds: position === "QB" || position === "RB" ? Math.round(projectedPoints / 38) : 0,
          receptions: position === "RB" || position === "WR" || position === "TE" ? Math.round(projectedPoints / 8) : 0,
          receivingYards: position === "RB" || position === "WR" || position === "TE" ? Math.round(projectedPoints * 3.4) : 0,
          receivingTds: position === "RB" || position === "WR" || position === "TE" ? Math.round(projectedPoints / 42) : 0,
          floor: Number((projectedPoints * 0.72).toFixed(1)),
          ceiling: Number((projectedPoints * 1.28).toFixed(1)),
          boomProb: 0.18,
          bustProb: 0.16,
          expectedPlays: position === "K" ? 0 : Math.round(420 - positionRank * 3),
          expectedRushPerPlay: 0,
          expectedTdPerPlay: 0,
        },
        history: [],
        analysis: "Local fallback mock draft player used when the backend player pool is unavailable.",
        sheetAdp: rank,
        sheetProjectedSeasonPoints: Number(projectedPoints.toFixed(1)),
      });
      id += 1;
      rank += 1;
    }
  }

  return rows;
};

const clampNumber = (value: number, min: number, max: number, fallback: number) => {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, Math.round(value)));
};

export const parseMockDraftSettings = (search = ""): MockDraftSettings => {
  const params = new URLSearchParams(search.startsWith("?") ? search : `?${search}`);
  return {
    leagueSize: clampNumber(Number(params.get("teams")), 8, 12, DEFAULT_MOCK_DRAFT_SETTINGS.leagueSize),
    rounds: MOCK_ROUNDS,
    pickTimerSeconds: clampNumber(Number(params.get("timer")), 15, 90, DEFAULT_MOCK_DRAFT_SETTINGS.pickTimerSeconds),
  };
};

export const getMockDraftSettings = (state?: Pick<SinglePlayerMockDraftState, "settings"> | null): MockDraftSettings => ({
  ...DEFAULT_MOCK_DRAFT_SETTINGS,
  ...(state?.settings ?? {}),
  rounds: MOCK_ROUNDS,
});

export const getMockTeamCount = (state?: Pick<SinglePlayerMockDraftState, "settings"> | null) =>
  getMockDraftSettings(state).leagueSize;

export const getMockRounds = (state?: Pick<SinglePlayerMockDraftState, "settings"> | null) =>
  getMockDraftSettings(state).rounds;

export const getMockPickTimerSeconds = (state?: Pick<SinglePlayerMockDraftState, "settings"> | null) =>
  getMockDraftSettings(state).pickTimerSeconds;

export const getMockTotalPicks = (state?: Pick<SinglePlayerMockDraftState, "settings"> | null) =>
  getMockTeamCount(state) * getMockRounds(state);

export const getMockUserTeamId = (leagueSize = MOCK_TEAM_COUNT) =>
  Math.min(Math.max(1, Math.ceil(leagueSize / 2)), leagueSize);

export const createMockTeams = (
  settings: MockDraftSettings = DEFAULT_MOCK_DRAFT_SETTINGS
): MockDraftTeam[] =>
  Array.from({ length: settings.leagueSize }, (_, index) => {
    const id = index + 1;
    const userTeamId = getMockUserTeamId(settings.leagueSize);
    return {
      id,
      name: id === userTeamId ? "Your Team" : `Bot Team ${id}`,
      managerType: id === userTeamId ? "user" : "bot",
    };
  });

export const createSinglePlayerMockDraft = (
  now = Date.now(),
  settings: MockDraftSettings = DEFAULT_MOCK_DRAFT_SETTINGS
): SinglePlayerMockDraftState => ({
  id: `local-${now}`,
  settings,
  status: "intermission",
  createdAt: now,
  intermissionEndsAt: now + MOCK_INTERMISSION_SECONDS * 1000,
  currentPick: 1,
  pickStartedAt: null,
  pickExpiresAt: null,
  userTeamId: getMockUserTeamId(settings.leagueSize),
  teams: createMockTeams(settings),
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
      state: createSinglePlayerMockDraft(now, parseMockDraftSettings(search)),
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

export const getRoundNumber = (overallPick: number, teamCount = MOCK_TEAM_COUNT) =>
  Math.floor((overallPick - 1) / Math.max(1, teamCount)) + 1;

export const getRoundPick = (overallPick: number, teamCount = MOCK_TEAM_COUNT) =>
  ((overallPick - 1) % Math.max(1, teamCount)) + 1;

export const getTeamIdForPick = (overallPick: number, teamCount = MOCK_TEAM_COUNT) => {
  const round = getRoundNumber(overallPick, teamCount);
  const roundPick = getRoundPick(overallPick, teamCount);
  return round % 2 === 1 ? roundPick : teamCount - roundPick + 1;
};

export const getCurrentTeam = (state: SinglePlayerMockDraftState) =>
  state.teams.find((team) => team.id === getTeamIdForPick(state.currentPick, getMockTeamCount(state)));

export const isUserOnClock = (state: SinglePlayerMockDraftState) =>
  state.status === "live" && getTeamIdForPick(state.currentPick, getMockTeamCount(state)) === state.userTeamId;

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

const draftedPlayerIdentityKeys = (state: SinglePlayerMockDraftState) =>
  new Set(state.picks.map((pick) => getDraftPlayerIdentityKey(pick)));

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
  const draftedIdentities = draftedPlayerIdentityKeys(state);
  return board
    .filter(
      (player) =>
        !drafted.has(player.id) && !draftedIdentities.has(getDraftPlayerIdentityKey(player))
    )
    .sort(compareDraftBoardPlayers);
};

export const getMockRosterPlayers = (
  state: SinglePlayerMockDraftState,
  teamId = getTeamIdForPick(state.currentPick, getMockTeamCount(state))
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
  teamId = getTeamIdForPick(state.currentPick, getMockTeamCount(state))
): PlayerPosition[] =>
  getLegalPositionsForRoster(getMockRosterPlayers(state, teamId), MOCK_ROSTER_SLOT_LIMITS);

export const getDraftablePlayersForTeam = (
  board: DraftPlayer[],
  state: SinglePlayerMockDraftState,
  teamId = getTeamIdForPick(state.currentPick, getMockTeamCount(state))
) =>
  filterDraftablePlayers(
    board,
    getMockRosterPlayers(state, teamId),
    MOCK_ROSTER_SLOT_LIMITS,
    draftedPlayerIds(state)
  )
    .filter((player) => !draftedPlayerIdentityKeys(state).has(getDraftPlayerIdentityKey(player)))
    .sort(compareDraftBoardPlayers);

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
  const teamCount = getMockTeamCount(state);
  const teamId = getTeamIdForPick(state.currentPick, teamCount);
  const team = state.teams.find((row) => row.id === teamId);
  return {
    overallPick: state.currentPick,
    round: getRoundNumber(state.currentPick, teamCount),
    roundPick: getRoundPick(state.currentPick, teamCount),
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
  pickExpiresAt: now + getMockPickTimerSeconds(state) * 1000,
});

const appendPick = (
  state: SinglePlayerMockDraftState,
  pick: MockDraftPick,
  now: number
): SinglePlayerMockDraftState => {
  const nextPick = state.currentPick + 1;
  const totalPicks = getMockTotalPicks(state);
  if (nextPick > totalPicks) {
    return {
      ...state,
      status: "complete",
      currentPick: totalPicks,
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
    const matchingPlayer = board.find((row) => row.id === playerId);
    const duplicateAlreadyDrafted =
      matchingPlayer !== undefined &&
      draftedPlayerIdentityKeys(state).has(getDraftPlayerIdentityKey(matchingPlayer));
    throw new Error(
      alreadyDrafted || duplicateAlreadyDrafted
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
  const totalPicks = getMockTotalPicks(nextState);
  while (nextState.status === "live" && guard < totalPicks) {
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
        currentPick: totalPicks,
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
