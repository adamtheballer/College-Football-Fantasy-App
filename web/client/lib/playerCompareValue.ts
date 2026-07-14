import { findCfb27Rating } from "@/lib/cfb27Ratings";
import type { Player } from "@/types/player";

export type CompareRow = Player & {
  compareRank: number;
  cfb27Overall: number | null;
  cfb27Rank: number | null;
  performanceAverage: number | null;
  valueOverall: number | null;
};

const VALUE_MODEL_WEEK = 1;

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

const average = (values: number[]) =>
  values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;

export const toProjectedPoints = (player: Player) =>
  player.sheetProjectedSeasonPoints ?? player.projection?.fpts ?? 0;

const normalizeCompareIdentityText = (value: string | null | undefined) =>
  (value ?? "")
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/\b(jr|jr\.|iii|ii|iv)\b/g, "")
    .replace(/[^a-z0-9]+/g, "")
    .trim();

const compareIdentityKey = (player: Player) =>
  [
    normalizeCompareIdentityText(player.name),
    normalizeCompareIdentityText(player.school),
    player.pos.toUpperCase(),
  ].join("|");

const hasRank = (player: Player) => {
  const rank = player.boardRank ?? player.rank ?? player.adp;
  return typeof rank === "number" && Number.isFinite(rank) && rank > 0;
};

const canonicalComparePlayer = (left: Player, right: Player) => {
  const leftHasRank = hasRank(left);
  const rightHasRank = hasRank(right);
  if (leftHasRank !== rightHasRank) return leftHasRank ? left : right;

  const leftRank = left.boardRank ?? left.rank ?? left.adp ?? Number.POSITIVE_INFINITY;
  const rightRank = right.boardRank ?? right.rank ?? right.adp ?? Number.POSITIVE_INFINITY;
  if (leftRank !== rightRank) return leftRank < rightRank ? left : right;

  return left.id <= right.id ? left : right;
};

export const dedupePlayerCompareRows = (players: Player[]) => {
  const byIdentity = new Map<string, Player>();
  for (const player of players) {
    const key = compareIdentityKey(player);
    const existing = byIdentity.get(key);
    byIdentity.set(key, existing ? canonicalComparePlayer(existing, player) : player);
  }
  return [...byIdentity.values()];
};

const getPerformanceAverage = (player: Player) => {
  const fantasyPoints = (player.history ?? [])
    .map((entry) => entry.stats?.fpts)
    .filter(isFiniteNumber);
  return average(fantasyPoints);
};

const percentileScore = (value: number | null, values: number[]) => {
  if (value === null || values.length === 0) return null;
  if (values.length === 1) return 0.5;
  const sorted = [...values].sort((left, right) => left - right);
  const lowerCount = sorted.filter((candidate) => candidate < value).length;
  const equalCount = sorted.filter((candidate) => candidate === value).length;
  return clamp((lowerCount + Math.max(equalCount - 1, 0) / 2) / (sorted.length - 1), 0, 1);
};

const projectionPerformanceScore = (actual: number | null, projected: number) => {
  if (actual === null || projected <= 0) return null;
  return clamp(0.5 + ((actual - projected) / projected) * 0.5, 0, 1);
};

export const getPlayerCompareValueWeights = (week = VALUE_MODEL_WEEK) => {
  const completedWeeks = clamp(Math.floor(week) - 1, 0, 12);
  const seasonShift = clamp(completedWeeks / 8, 0, 1);

  return {
    cfb27: 1 - seasonShift * 0.55,
    weeklyPerformance: seasonShift * 0.3,
    positionPeer: seasonShift * 0.15,
    projectionPerformance: seasonShift * 0.1,
  };
};

const weightedOverall = ({
  cfb27Score,
  weeklyPerformanceScore,
  positionPeerScore,
  projectionScore,
  week,
}: {
  cfb27Score: number | null;
  weeklyPerformanceScore: number | null;
  positionPeerScore: number | null;
  projectionScore: number | null;
  week: number;
}) => {
  const weights = getPlayerCompareValueWeights(week);
  const weightedParts = [
    { score: cfb27Score, weight: weights.cfb27 },
    { score: weeklyPerformanceScore, weight: weights.weeklyPerformance },
    { score: positionPeerScore, weight: weights.positionPeer },
    { score: projectionScore, weight: weights.projectionPerformance },
  ].filter((part): part is { score: number; weight: number } => part.score !== null && part.weight > 0);

  const totalWeight = weightedParts.reduce((total, part) => total + part.weight, 0);
  if (totalWeight <= 0) return null;

  const score = weightedParts.reduce((total, part) => total + part.score * part.weight, 0) / totalWeight;
  return clamp(Math.round(score * 99), 1, 99);
};

export const buildPlayerCompareRows = (
  players: Player[],
  { week = VALUE_MODEL_WEEK }: { week?: number } = {}
): CompareRow[] => {
  const canonicalPlayers = dedupePlayerCompareRows(players);
  const performanceByPlayerId = new Map(
    canonicalPlayers.map((player) => [player.id, getPerformanceAverage(player)])
  );
  const performanceValues = [...performanceByPlayerId.values()].filter(isFiniteNumber);
  const performanceByPosition = canonicalPlayers.reduce((map, player) => {
    const value = performanceByPlayerId.get(player.id);
    if (!isFiniteNumber(value)) return map;
    map.set(player.pos, [...(map.get(player.pos) ?? []), value]);
    return map;
  }, new Map<string, number[]>());

  return canonicalPlayers
    .map((player) => {
      const cfb27Rating = findCfb27Rating({
        name: player.name,
        school: player.school,
        pos: player.pos,
      });
      const performanceAverage = performanceByPlayerId.get(player.id) ?? null;
      const weeklyPerformanceScore = percentileScore(performanceAverage, performanceValues);
      const positionPeerScore = percentileScore(
        performanceAverage,
        performanceByPosition.get(player.pos) ?? []
      );
      const projectionScore = projectionPerformanceScore(performanceAverage, toProjectedPoints(player));
      const valueOverall = weightedOverall({
        cfb27Score: cfb27Rating ? cfb27Rating.ovr / 99 : null,
        weeklyPerformanceScore,
        positionPeerScore,
        projectionScore,
        week,
      });

      return {
        ...player,
        cfb27Overall: cfb27Rating?.ovr ?? null,
        cfb27Rank: cfb27Rating?.rank ?? null,
        performanceAverage,
        valueOverall,
        compareRank: 0,
      };
    })
    .sort((left, right) => {
      if ((right.valueOverall ?? -1) !== (left.valueOverall ?? -1)) {
        return (right.valueOverall ?? -1) - (left.valueOverall ?? -1);
      }
      if ((right.cfb27Overall ?? -1) !== (left.cfb27Overall ?? -1)) {
        return (right.cfb27Overall ?? -1) - (left.cfb27Overall ?? -1);
      }
      return (
        (left.boardRank ?? left.rank ?? 999) - (right.boardRank ?? right.rank ?? 999) ||
        left.name.localeCompare(right.name)
      );
    })
    .map((row, index) => ({ ...row, compareRank: index + 1 }));
};
