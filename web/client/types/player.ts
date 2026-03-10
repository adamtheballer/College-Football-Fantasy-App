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
  conf: string;
  rank: number;
  adp: number;
  posRank: number;
  rostered: number;
  status: "HEALTHY" | "OUT" | "QUESTIONABLE" | "DOUBTFUL" | "IR";
  projection: PlayerStats;
  history: PlayerHistory[];
  analysis: string;
  number?: number;
}
