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
  adp: number;
  posRank: number | null;
  rostered: number;
  status: "HEALTHY" | "OUT" | "QUESTIONABLE" | "DOUBTFUL" | "IR";
  projection: PlayerStats;
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
  number?: number;
}
