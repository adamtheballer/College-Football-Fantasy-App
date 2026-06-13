import type { Player } from "@/types/player";

export type DraftBoardMode = "single_mock" | "multiplayer_mock" | "real";

export type DraftBoardParticipant = {
  id: number;
  name: string;
  teamName: string;
  participantType: "human" | "bot";
  userId: number | null;
  draftPosition: number | null;
  isCurrent: boolean;
  isUser: boolean;
};

export type DraftBoardPick = {
  id: number;
  overallPick: number;
  roundNumber: number;
  roundPick: number;
  participantId: number;
  participantName: string;
  teamName: string;
  playerId: number;
  playerName: string;
  playerPosition: string;
  playerSchool: string;
  pickSource: string;
  createdAt: string;
};

export type DraftBoardRoster = {
  participantId: number;
  participantName: string;
  teamName: string;
  picks: DraftBoardPick[];
};

export type DraftBoardPlayer = {
  id: number;
  rank: number;
  boardRank?: number | null;
  name: string;
  school: string;
  position: string;
  projection?: number | null;
  adp?: number | null;
  rosteredPercent?: number | null;
  team?: string | null;
  disabled?: boolean;
  sourcePlayer?: Player;
};

export type DraftBoardState = {
  mode: DraftBoardMode;
  title: string;
  subtitle: string;
  status: string;
  phaseType?: string | null;
  currentOverallPick: number;
  totalPicks: number;
  currentRound: number;
  currentRoundPick: number;
  currentParticipantName: string | null;
  currentParticipantType: "human" | "bot" | string | null;
  currentTeamName: string | null;
  secondsRemaining: number | null;
  formattedTime: string;
  isUserOnClock: boolean;
  isComplete: boolean;
  participants: DraftBoardParticipant[];
  picks: DraftBoardPick[];
  rosters?: DraftBoardRoster[];
  availablePlayers: DraftBoardPlayer[];
  userRoster?: DraftBoardPick[];
  lastPick?: DraftBoardPick | null;
};
