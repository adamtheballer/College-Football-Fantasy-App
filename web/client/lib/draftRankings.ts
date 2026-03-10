import { Player } from "@/types/player";

export type DraftRosterSlots = {
  QB: number;
  RB: number;
  WR: number;
  TE: number;
  FLEX: number;
  K: number;
  BE: number;
  IR: number;
};

export type DraftConfig = {
  leagueSize: number;
  rosterSlots: DraftRosterSlots;
};

export type DraftPlayer = Player & {
  draftRank: number;
  adpRank: number;
  adpEstimate: number;
  projectedPoints: number;
  tier: number;
  tprScore: number;
  marScore: number;
};

const POWER4_CONFS = new Set(["SEC", "Big Ten", "Big 12", "ACC"]);
const DRAFT_POSITIONS = new Set(["QB", "RB", "WR", "TE", "K"]);
const SEASON_GAMES = 12;

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

const mean = (values: number[]) => {
  if (!values.length) return 0;
  return values.reduce((sum, v) => sum + v, 0) / values.length;
};

const std = (values: number[]) => {
  if (values.length <= 1) return 1;
  const avg = mean(values);
  const variance = values.reduce((sum, v) => sum + (v - avg) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance) || 1;
};

const zScore = (value: number, values: number[]) => {
  const avg = mean(values);
  const sd = std(values);
  return sd === 0 ? 0 : (value - avg) / sd;
};

const erf = (x: number) => {
  const sign = x < 0 ? -1 : 1;
  const absX = Math.abs(x);
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;
  const t = 1 / (1 + p * absX);
  const y =
    1 -
    (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t) *
      Math.exp(-absX * absX);
  return sign * y;
};

const normalCdf = (x: number, meanValue: number, sd: number) => {
  if (sd <= 0) return 0.5;
  const z = (x - meanValue) / (sd * Math.SQRT2);
  return 0.5 * (1 + erf(z));
};

const varianceByPos: Record<string, number> = {
  QB: 0.24,
  RB: 0.30,
  WR: 0.32,
  TE: 0.30,
  K: 0.18,
};

const espnFantasyPoints = (player: Player) => {
  const proj = player.projection || {};
  const passYds = proj.passingYards ?? 0;
  const passTds = proj.passingTds ?? 0;
  const ints = proj.ints ?? 0;
  const rushYds = proj.rushingYards ?? 0;
  const rushTds = proj.rushingTds ?? 0;
  const recs = proj.receptions ?? 0;
  const recYds = proj.receivingYards ?? 0;
  const recTds = proj.receivingTds ?? 0;

  if (player.pos === "K") {
    return proj.fpts ?? 0;
  }

  return (
    passYds / 25 +
    passTds * 4 +
    ints * -2 +
    rushYds / 10 +
    rushTds * 6 +
    recs * 1 +
    recYds / 10 +
    recTds * 6
  );
};

const historyFantasyPoints = (player: Player) => {
  const latest = player.history?.[0]?.stats;
  if (!latest) return 0;
  if (latest.fpts !== undefined) return latest.fpts;
  const passYds = latest.passingYards ?? 0;
  const passTds = latest.passingTds ?? 0;
  const ints = latest.ints ?? 0;
  const rushYds = latest.rushingYards ?? 0;
  const rushTds = latest.rushingTds ?? 0;
  const recs = latest.receptions ?? 0;
  const recYds = latest.receivingYards ?? 0;
  const recTds = latest.receivingTds ?? 0;
  return (
    passYds / 25 +
    passTds * 4 +
    ints * -2 +
    rushYds / 10 +
    rushTds * 6 +
    recs * 1 +
    recYds / 10 +
    recTds * 6
  );
};

const FLEX_DISTRIBUTION: Record<string, number> = {
  RB: 0.45,
  WR: 0.45,
  TE: 0.10,
};

const BENCH_DISTRIBUTION: Record<string, number> = {
  QB: 0.10,
  RB: 0.35,
  WR: 0.35,
  TE: 0.10,
  K: 0.05,
  FLEX: 0.05,
};

const positionMultiplier: Record<string, number> = {
  QB: 0.92,
  RB: 1.05,
  WR: 1.03,
  TE: 1.02,
  K: 0.65,
};

const computeReplacementIndex = (
  pos: string,
  leagueSize: number,
  rosterSlots: DraftRosterSlots
) => {
  const starters = (rosterSlots[pos as keyof DraftRosterSlots] || 0) * leagueSize;
  const flexSlots = rosterSlots.FLEX * leagueSize;
  const benchSlots = (rosterSlots.BE + rosterSlots.IR) * leagueSize;

  const flexShare = FLEX_DISTRIBUTION[pos] ? flexSlots * FLEX_DISTRIBUTION[pos] : 0;
  const benchShare = BENCH_DISTRIBUTION[pos] ? benchSlots * BENCH_DISTRIBUTION[pos] : 0;

  return Math.max(1, Math.round(starters + flexShare + benchShare));
};

export const buildDraftBoard = (players: Player[], config: DraftConfig): DraftPlayer[] => {
  const eligible = players
    .filter((p) => POWER4_CONFS.has(p.conf))
    .filter((p) => DRAFT_POSITIONS.has(p.pos));

  const projectedPointsByPos: Record<string, number[]> = {};
  const historyPointsByPos: Record<string, number[]> = {};
  const projectedPointsAll: number[] = [];
  const scarcityAll: number[] = [];

  const withPoints = eligible.map((player) => {
    const projectedPoints = espnFantasyPoints(player);
    const historyPoints = historyFantasyPoints(player);
    projectedPointsAll.push(projectedPoints);
    projectedPointsByPos[player.pos] = projectedPointsByPos[player.pos] || [];
    projectedPointsByPos[player.pos].push(projectedPoints);
    historyPointsByPos[player.pos] = historyPointsByPos[player.pos] || [];
    historyPointsByPos[player.pos].push(historyPoints);
    return { player, projectedPoints, historyPoints };
  });

  const replacementByPos: Record<string, number> = {};
  Object.entries(projectedPointsByPos).forEach(([pos, values]) => {
    const sorted = [...values].sort((a, b) => b - a);
    const replacementIndex = computeReplacementIndex(pos, config.leagueSize, config.rosterSlots);
    const idx = clamp(replacementIndex - 1, 0, sorted.length - 1);
    replacementByPos[pos] = sorted[idx] ?? 0;
  });

  const evaluated = withPoints.map(({ player, projectedPoints, historyPoints }) => {
    const replacement = replacementByPos[player.pos] ?? 0;
    const scarcity = projectedPoints - replacement;
    scarcityAll.push(scarcity);

    const posRank = player.posRank || 20;
    const roleCertainty = clamp(1 - (posRank - 1) / 30, 0.4, 0.95);

    const expectedPlays = player.projection?.expectedPlays ?? 0;
    const maxExpectedPlays = Math.max(
      1,
      ...(eligible.map((p) => p.projection?.expectedPlays ?? 0))
    );
    const environmentScore = clamp(expectedPlays / maxExpectedPlays, 0.4, 1.1);

    const floor = player.projection?.floor ?? projectedPoints * 0.7;
    const ceiling = player.projection?.ceiling ?? projectedPoints * 1.3;
    const spread = Math.max(1, ceiling - floor);
    const maxSpread = Math.max(
      1,
      ...(eligible.map((p) => {
        const f = p.projection?.floor ?? 0;
        const c = p.projection?.ceiling ?? 0;
        return Math.max(1, c - f);
      }))
    );
    const consistency = clamp(1 - spread / maxSpread, 0.2, 0.9);

    const injuryPenalty = player.status && player.status !== "HEALTHY" ? 0.05 : 0.0;
    const committeePenalty = ["RB", "WR", "TE"].includes(player.pos) ? (1 - roleCertainty) * 0.05 : 0.0;

    return {
      player,
      projectedPoints,
      historyPoints,
      scarcity,
      roleCertainty,
      environmentScore,
      consistency,
      injuryPenalty,
      committeePenalty,
    };
  });

  const tprScores = evaluated.map((entry) => {
    const projZ = zScore(entry.projectedPoints, projectedPointsAll);
    const scarcityZ = zScore(entry.scarcity, scarcityAll);
    const historyZ = zScore(entry.historyPoints, historyPointsByPos[entry.player.pos] || []);
    const baseScore =
      0.55 * projZ +
      0.15 * scarcityZ +
      0.10 * entry.roleCertainty +
      0.10 * historyZ +
      0.05 * entry.environmentScore +
      0.05 * entry.consistency;

    const penalty = entry.injuryPenalty + entry.committeePenalty;
    const positionAdjust = positionMultiplier[entry.player.pos] ?? 1;
    return {
      ...entry,
      tprScore: (baseScore - penalty) * positionAdjust,
    };
  });

  const marScores = tprScores.map((entry) => {
    const historyZ = zScore(entry.historyPoints, historyPointsByPos[entry.player.pos] || []);
    const projZ = zScore(entry.projectedPoints, projectedPointsAll);
    const adp = entry.player.adp ?? 0;
    const adpScore = adp > 0 ? -adp / 100 : projZ;
    const marketProxy = 0.45 * historyZ + 0.35 * projZ + 0.20 * entry.roleCertainty;
    return {
      ...entry,
      marScore: 0.45 * marketProxy + 0.30 * adpScore + 0.15 * projZ,
    };
  });

  const tprSorted = [...marScores].sort((a, b) => b.tprScore - a.tprScore);
  const marSorted = [...marScores].sort((a, b) => b.marScore - a.marScore);

  const adpRankById = new Map<number, number>();
  marSorted.forEach((entry, idx) => {
    adpRankById.set(entry.player.id, idx + 1);
  });

  const withRanks = tprSorted.map((entry, idx) => {
    const adpRank = adpRankById.get(entry.player.id) || idx + 1;
    const projectedPoints = entry.projectedPoints;
    const adpEstimate = entry.player.adp && entry.player.adp > 0 ? entry.player.adp : adpRank;
    return {
      ...entry,
      draftRank: idx + 1,
      adpRank,
      adpEstimate,
      projectedPoints,
      tier: 1,
    };
  });

  let currentTier = 1;
  let tierStartIndex = 0;
  withRanks.forEach((entry, idx) => {
    if (idx === 0) {
      entry.tier = currentTier;
      return;
    }
    const prev = withRanks[idx - 1];
    const drop = prev.projectedPoints > 0 ? (prev.projectedPoints - entry.projectedPoints) / prev.projectedPoints : 0;
    const tierSize = idx - tierStartIndex;
    if (drop >= 0.12 && tierSize >= 4) {
      currentTier += 1;
      tierStartIndex = idx;
    }
    entry.tier = currentTier;
  });

  return withRanks.map((entry) => {
    const perGame = entry.projectedPoints / SEASON_GAMES;
    const baseVar = varianceByPos[entry.player.pos] ?? 0.26;
    const rolePenalty = 1 + (1 - entry.roleCertainty) * 0.8;
    const sdPerGame = Math.max(3, perGame * baseVar * rolePenalty);
    const seasonSd = sdPerGame * Math.sqrt(SEASON_GAMES);
    const floor = Math.max(0, entry.projectedPoints - seasonSd);
    const ceiling = entry.projectedPoints + seasonSd;
    const boomProb = 1 - normalCdf(entry.projectedPoints + seasonSd * 0.75, entry.projectedPoints, seasonSd);
    const bustProb = normalCdf(entry.projectedPoints - seasonSd * 0.75, entry.projectedPoints, seasonSd);

    const updatedProjection = {
      ...entry.player.projection,
      fpts: Number(entry.projectedPoints.toFixed(1)),
      floor: Number((floor / SEASON_GAMES).toFixed(1)),
      ceiling: Number((ceiling / SEASON_GAMES).toFixed(1)),
      boomProb: Number(clamp(boomProb, 0.05, 0.65).toFixed(2)),
      bustProb: Number(clamp(bustProb, 0.05, 0.65).toFixed(2)),
    };
    return {
      ...entry.player,
      projection: updatedProjection,
      draftRank: entry.draftRank,
      adpRank: entry.adpRank,
      adpEstimate: entry.adpEstimate,
      projectedPoints: Number(entry.projectedPoints.toFixed(1)),
      tier: entry.tier,
      tprScore: entry.tprScore,
      marScore: entry.marScore,
    };
  });
};
