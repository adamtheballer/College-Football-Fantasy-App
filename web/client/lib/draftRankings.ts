import { Player } from "@/types/player";
import { PlayerStats } from "@/types/player";
import { findCfb27Rating, getCfb27PositionPercentile } from "@/lib/cfb27Ratings";

export type DraftRosterSlots = {
  QB: number;
  RB: number;
  WR: number;
  TE: number;
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
  masterDraftRank: number;
  sourceBoardRank: number | null;
  adpRank: number;
  adpEstimate: number;
  projectedPoints: number;
  tier: number;
  tprScore: number;
  marScore: number;
  finalDraftScore: number;
  cfb27Overall: number | null;
  cfb27TalentScore: number;
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

const percentileFromValue = (value: number, values: number[]) => {
  if (!values.length) return 0.5;
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (max === min) return 0.5;
  return clamp((value - min) / (max - min), 0, 1);
};

const percentileFromRank = (rank: number | null | undefined, total: number) => {
  if (!rank || !Number.isFinite(rank) || rank <= 0 || total <= 1) return 0.5;
  return clamp(1 - (rank - 1) / (total - 1), 0, 1);
};

const varianceByPos: Record<string, number> = {
  QB: 0.24,
  RB: 0.30,
  WR: 0.32,
  TE: 0.30,
  K: 0.18,
};

const espnFantasyPoints = (player: Player) => {
  if (
    typeof player.sheetProjectedSeasonPoints === "number" &&
    Number.isFinite(player.sheetProjectedSeasonPoints) &&
    player.sheetProjectedSeasonPoints > 0
  ) {
    return player.sheetProjectedSeasonPoints;
  }

  const proj: Partial<PlayerStats> = player.projection || {};
  const passYds = proj.passingYards ?? 0;
  const passTds = proj.passingTds ?? 0;
  const ints = proj.ints ?? 0;
  const rushYds = proj.rushingYards ?? 0;
  const rushTds = proj.rushingTds ?? 0;
  const recs = proj.receptions ?? 0;
  const recYds = proj.receivingYards ?? 0;
  const recTds = proj.receivingTds ?? 0;
  const projectedFantasyPoints =
    typeof proj.fpts === "number" && Number.isFinite(proj.fpts) && proj.fpts > 0
      ? proj.fpts
      : null;

  if (projectedFantasyPoints !== null) {
    return projectedFantasyPoints;
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
  const latest: Partial<PlayerStats> | undefined = player.history?.[0]?.stats;
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

const BENCH_DISTRIBUTION: Record<string, number> = {
  QB: 0.10,
  RB: 0.35,
  WR: 0.35,
  TE: 0.10,
  K: 0.05,
};

const positionMultiplier: Record<string, number> = {
  QB: 0.92,
  RB: 1.05,
  WR: 1.03,
  TE: 1.02,
  K: 0.65,
};

const SKILL_POSITIONS = new Set(["RB", "WR", "TE"]);
const WR_VALUE_PENALTY_START = 15;
const WR_VALUE_PENALTY_SLOTS = 2;
const QB_BACKUP_MIN_PROJECTION = 60;
const QB_BACKUP_REPLACEMENT_RATE = 0.4;
const QB_STARTER_PROJECTION_FLOOR = 180;
const QB_SOURCE_RANK_OUTLIER_GAP = 24;
const QB_PROJECTION_RANK_BUFFER = 12;

const getProvidedBoardRank = (player: Player) => {
  const candidates = [player.boardRank, player.adp, player.rank];
  const value = candidates.find(
    (candidate): candidate is number =>
      typeof candidate === "number" && Number.isFinite(candidate) && candidate > 0
  );
  return value ? Math.round(value) : null;
};

const computeReplacementIndex = (
  pos: string,
  leagueSize: number,
  rosterSlots: DraftRosterSlots
) => {
  const starters = (rosterSlots[pos as keyof DraftRosterSlots] || 0) * leagueSize;
  const benchSlots = (rosterSlots.BE + rosterSlots.IR) * leagueSize;

  const benchShare = BENCH_DISTRIBUTION[pos] ? benchSlots * BENCH_DISTRIBUTION[pos] : 0;

  return Math.max(1, Math.round(starters + benchShare));
};

const isLowProjectionQb = (
  entry: { player: Player; projectedPoints: number },
  qbReplacementPoints: number
) =>
  entry.player.pos === "QB" &&
  entry.projectedPoints <
    Math.max(QB_BACKUP_MIN_PROJECTION, qbReplacementPoints * QB_BACKUP_REPLACEMENT_RATE);

const getProjectionAwareProvidedRank = (
  entry: { player: Player; projectedPoints: number },
  computedRank: number,
  qbReplacementPoints: number
) => {
  const providedRank = getProvidedBoardRank(entry.player);
  if (providedRank === null) return null;
  if (entry.player.pos !== "QB") return providedRank;
  if (isLowProjectionQb(entry, qbReplacementPoints)) return providedRank;

  const starterProjectionCutoff = Math.max(
    QB_STARTER_PROJECTION_FLOOR,
    qbReplacementPoints * 0.85
  );
  const sourceIsClearlyStale =
    providedRank - computedRank >= QB_SOURCE_RANK_OUTLIER_GAP &&
    entry.projectedPoints >= starterProjectionCutoff;

  if (!sourceIsClearlyStale) return providedRank;
  return Math.min(providedRank, computedRank + QB_PROJECTION_RANK_BUFFER);
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
    const cfb27Rating = findCfb27Rating({
      name: player.name,
      school: player.school,
      pos: player.pos,
    });
    const cfb27TalentScore = getCfb27PositionPercentile(cfb27Rating);

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
      cfb27Rating,
      cfb27TalentScore,
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

  const computedSorted = [...marScores].sort((a, b) => b.tprScore - a.tprScore);
  const marSorted = [...marScores].sort((a, b) => b.marScore - a.marScore);

  const adpRankById = new Map<number, number>();
  marSorted.forEach((entry, idx) => {
    adpRankById.set(entry.player.id, idx + 1);
  });

  const computedRankById = new Map<number, number>();
  computedSorted.forEach((entry, index) => {
    computedRankById.set(entry.player.id, index + 1);
  });

  const maxProvidedRank = Math.max(
    0,
    ...marScores.map((entry) => getProvidedBoardRank(entry.player) ?? 0)
  );

  const qbReplacementPoints = replacementByPos.QB ?? 0;

  const scoredBoard = marScores.map((entry) => {
    const computedRank = computedRankById.get(entry.player.id) ?? marScores.length;
    const providedRank = getProjectionAwareProvidedRank(entry, computedRank, qbReplacementPoints);
    const fantasyProjectionScore =
      0.65 * percentileFromValue(entry.scarcity, scarcityAll) +
      0.35 * percentileFromValue(entry.projectedPoints, projectedPointsAll);
    const marketRankScore =
      0.60 * percentileFromRank(computedRank, marScores.length) +
      0.40 * percentileFromRank(providedRank ?? getProvidedBoardRank(entry.player), marScores.length);
    const riskPenalty = entry.injuryPenalty + entry.committeePenalty;
    const finalDraftScore =
      0.60 * fantasyProjectionScore +
      0.20 * marketRankScore +
      0.12 * entry.cfb27TalentScore +
      0.08 * entry.roleCertainty -
      riskPenalty;

    return {
      ...entry,
      finalDraftScore,
    };
  });

  const providedBoardSorted = [...scoredBoard].sort((left, right) => {
    const leftLowProjectionQb = isLowProjectionQb(left, qbReplacementPoints);
    const rightLowProjectionQb = isLowProjectionQb(right, qbReplacementPoints);
    if (leftLowProjectionQb !== rightLowProjectionQb) {
      return leftLowProjectionQb ? 1 : -1;
    }
    if (leftLowProjectionQb && rightLowProjectionQb) {
      if (left.projectedPoints !== right.projectedPoints) {
        return right.projectedPoints - left.projectedPoints;
      }
    }

    if (left.finalDraftScore !== right.finalDraftScore) {
      return right.finalDraftScore - left.finalDraftScore;
    }

    const leftComputedRank = computedRankById.get(left.player.id) ?? Number.POSITIVE_INFINITY;
    const rightComputedRank = computedRankById.get(right.player.id) ?? Number.POSITIVE_INFINITY;
    return leftComputedRank - rightComputedRank;
  });

  const prePenaltyRanks = providedBoardSorted.map((entry, idx) => {
    const providedRank = getProvidedBoardRank(entry.player);
    const computedRank = computedRankById.get(entry.player.id) ?? idx + 1;
    const projectionAwareRank = getProjectionAwareProvidedRank(
      entry,
      computedRank,
      qbReplacementPoints
    );
    const adpRank = adpRankById.get(entry.player.id) || idx + 1;
    const projectedPoints = entry.projectedPoints;
    const adpEstimate = providedRank ?? adpRank;
    return {
      ...entry,
      sourceBoardRank: providedRank,
      prePenaltyRank: projectionAwareRank ?? maxProvidedRank + computedRank,
      adpRank,
      adpEstimate,
      projectedPoints,
      tier: 1,
    };
  });

  const lowProjectionQbRanks = prePenaltyRanks
    .filter((entry) => isLowProjectionQb(entry, qbReplacementPoints))
    .sort((left, right) => {
      if (left.projectedPoints !== right.projectedPoints) {
        return right.projectedPoints - left.projectedPoints;
      }
      return (left.sourceBoardRank ?? Number.POSITIVE_INFINITY) - (right.sourceBoardRank ?? Number.POSITIVE_INFINITY);
    });
  const draftablePrePenaltyRanks = prePenaltyRanks.filter(
    (entry) => !isLowProjectionQb(entry, qbReplacementPoints)
  );

  const topLocked = draftablePrePenaltyRanks.slice(0, WR_VALUE_PENALTY_START);
  const penaltyEligible = draftablePrePenaltyRanks
    .slice(WR_VALUE_PENALTY_START)
    .map((entry, index) => ({
      entry,
      originalIndex: WR_VALUE_PENALTY_START + index + 1,
      adjustedIndex:
        WR_VALUE_PENALTY_START +
        index +
        1 +
        (entry.player.pos === "WR" ? WR_VALUE_PENALTY_SLOTS : 0),
    }))
    .sort((left, right) => {
      if (left.adjustedIndex !== right.adjustedIndex) {
        return left.adjustedIndex - right.adjustedIndex;
      }
      return left.originalIndex - right.originalIndex;
    })
    .map(({ entry }) => entry);

  const withRanks = [...topLocked, ...penaltyEligible, ...lowProjectionQbRanks].map((entry, index) => ({
    ...entry,
    draftRank: index + 1,
    masterDraftRank: index + 1,
  }));

  const adjustedProjectionById = new Map<number, number>();
  for (const position of SKILL_POSITIONS) {
    let previousProjection = Number.POSITIVE_INFINITY;
    withRanks
      .filter((entry) => entry.player.pos === position)
      .sort((left, right) => left.draftRank - right.draftRank)
      .forEach((entry) => {
        const adjustedProjection =
          entry.projectedPoints >= previousProjection
            ? Math.max(0, previousProjection - 0.1)
            : entry.projectedPoints;
        adjustedProjectionById.set(entry.player.id, Number(adjustedProjection.toFixed(1)));
        previousProjection = adjustedProjection;
      });
  }

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
    const projectedPoints = adjustedProjectionById.get(entry.player.id) ?? entry.projectedPoints;
    const perGame = projectedPoints / SEASON_GAMES;
    const baseVar = varianceByPos[entry.player.pos] ?? 0.26;
    const rolePenalty = 1 + (1 - entry.roleCertainty) * 0.8;
    const sdPerGame = Math.max(3, perGame * baseVar * rolePenalty);
    const seasonSd = sdPerGame * Math.sqrt(SEASON_GAMES);
    const floor = Math.max(0, projectedPoints - seasonSd);
    const ceiling = projectedPoints + seasonSd;
    const boomProb = 1 - normalCdf(projectedPoints + seasonSd * 0.75, projectedPoints, seasonSd);
    const bustProb = normalCdf(projectedPoints - seasonSd * 0.75, projectedPoints, seasonSd);

    const updatedProjection = {
      ...entry.player.projection,
      fpts: Number(projectedPoints.toFixed(1)),
      floor: Number((floor / SEASON_GAMES).toFixed(1)),
      ceiling: Number((ceiling / SEASON_GAMES).toFixed(1)),
      boomProb: Number(clamp(boomProb, 0.05, 0.65).toFixed(2)),
      bustProb: Number(clamp(bustProb, 0.05, 0.65).toFixed(2)),
    };
    return {
      ...entry.player,
      projection: updatedProjection,
      draftRank: entry.draftRank,
      masterDraftRank: entry.masterDraftRank,
      sourceBoardRank: entry.sourceBoardRank,
      adpRank: entry.adpRank,
      adpEstimate: entry.adpEstimate,
      projectedPoints: Number(projectedPoints.toFixed(1)),
      tier: entry.tier,
      tprScore: entry.tprScore,
      marScore: entry.marScore,
      finalDraftScore: Number(entry.finalDraftScore.toFixed(4)),
      cfb27Overall: entry.cfb27Rating?.ovr ?? null,
      cfb27TalentScore: Number(entry.cfb27TalentScore.toFixed(4)),
    };
  });
};
