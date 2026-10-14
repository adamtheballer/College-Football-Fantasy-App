export interface PlayerStats {
  passingYards?: number;
  passingTds?: number;
  ints?: number;
  rushingYards?: number;
  rushingTds?: number;
  receptions?: number;
  receivingYards?: number;
  receivingTds?: number;
  fpts: number;
  qbr?: number;
  expectedPlays?: number;
  expectedRushPerPlay?: number;
  expectedTdPerPlay?: number;
  floor?: number;
  ceiling?: number;
  boomProb?: number;
  bustProb?: number;
}

export interface PlayerHistory {
  year: number;
  stats: PlayerStats;
}

export interface Player {
  id: number;
  name: string;
  school: string;
  pos: string;
  imageUrl?: string;
  playerClass?: string;
  conf: string;
  rank: number;
  boardRank?: number | null;
  masterDraftRank?: number | null;
  draftProjectedPoints?: number | null;
  draftProjectionMissing?: boolean;
  draftSourceRank?: number | null;
  draftTier?: number | null;
  draftFinalScore?: number | null;
  draftTalentScore?: number | null;
  draftRankingVersion?: string | null;
  adp: number;
  posRank: number | null;
  rostered: number;
  status: "HEALTHY" | "OUT" | "OUT_FOR_SEASON" | "QUESTIONABLE" | "DOUBTFUL" | "PROBABLE" | "DAY_TO_DAY" | "SUSPENDED" | "INACTIVE" | "TBD" | "IR" | "UNREPORTED";
  projection: PlayerStats;
  hasWeeklyProjection?: boolean;
  history: PlayerHistory[];
  analysis: string;
  sheetAdp?: number;
  sheetProjectedSeasonPoints?: number;
  sheetProjectionStats?: Record<string, number | null | undefined>;
  sheetSourceSheetId?: string;
  sheetSyncedAt?: string;
  cfb27Rank?: number;
  cfb27Overall?: number;
  cfb27PositionRank?: number;
  cfb27SyncedAt?: string;
  restOfSeasonProjectedPoints?: number;
  restOfSeasonRank?: number;
  restOfSeasonAsOfWeek?: number;
  restOfSeasonUpdatedAt?: string;
  number?: number;
}
