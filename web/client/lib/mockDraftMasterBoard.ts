import { CFB27_RATINGS } from "@/lib/cfb27Ratings";
import { getDraftPlayerIdentityKey } from "@/lib/draftRankings";
import type { Player } from "@/types/player";

const baseProjectionByPosition: Record<string, number> = {
  QB: 250,
  RB: 220,
  WR: 220,
  TE: 140,
  K: 90,
};

const projectionStepByPosition: Record<string, number> = {
  QB: 4,
  RB: 5,
  WR: 5,
  TE: 3.5,
  K: 2,
};

const globalCfb27RankByKey = new Map(
  [...CFB27_RATINGS]
    .sort((left, right) => {
      if (left.ovr !== right.ovr) return right.ovr - left.ovr;
      if (left.rank !== right.rank) return left.rank - right.rank;
      return left.name.localeCompare(right.name);
    })
    .map((rating, index) => [getDraftPlayerIdentityKey(rating), index + 1])
);

const cfb27RatingByKey = new Map(
  CFB27_RATINGS.map((rating) => [getDraftPlayerIdentityKey(rating), rating])
);

const fallbackProjection = (position: string, overall: number) => {
  const base = baseProjectionByPosition[position] ?? 120;
  const step = projectionStepByPosition[position] ?? 2;
  return Number((base + Math.max(0, overall - 75) * step).toFixed(1));
};

const hasPositiveNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value > 0;

const enrichCfb27DraftPlayer = (player: Player): Player => {
  const identityKey = getDraftPlayerIdentityKey(player);
  const rating = cfb27RatingByKey.get(identityKey);
  const masterRank = globalCfb27RankByKey.get(identityKey);

  if (!rating || !masterRank) {
    return player;
  }

  const existingProjection = player.projection?.fpts;
  const projectedPoints = hasPositiveNumber(player.sheetProjectedSeasonPoints)
    ? player.sheetProjectedSeasonPoints
    : hasPositiveNumber(existingProjection)
      ? existingProjection
      : fallbackProjection(rating.pos, rating.ovr);
  const floor = hasPositiveNumber(player.projection?.floor)
    ? player.projection.floor
    : Number((projectedPoints * 0.7).toFixed(1));
  const ceiling = hasPositiveNumber(player.projection?.ceiling)
    ? player.projection.ceiling
    : Number((projectedPoints * 1.25).toFixed(1));

  return {
    ...player,
    rank: masterRank,
    boardRank: masterRank,
    adp: masterRank,
    posRank: rating.rank,
    sheetAdp: masterRank,
    sheetProjectedSeasonPoints: projectedPoints,
    projection: {
      ...player.projection,
      fpts: projectedPoints,
      floor,
      ceiling,
    },
  };
};

export function enrichCfb27DraftPlayers(existingPlayers: Player[]): Player[] {
  return existingPlayers.map(enrichCfb27DraftPlayer);
}

export function createMissingCfb27MockDraftPlayers(existingPlayers: Player[]): Player[] {
  const existingKeys = new Set(existingPlayers.map((player) => getDraftPlayerIdentityKey(player)));

  return CFB27_RATINGS.filter((rating) => !existingKeys.has(getDraftPlayerIdentityKey(rating))).map(
    (rating, index): Player => {
      const rank = globalCfb27RankByKey.get(getDraftPlayerIdentityKey(rating)) ?? 1000 + index;
      const projectedPoints = fallbackProjection(rating.pos, rating.ovr);
      return {
        id: -1_000_000 - index,
        name: rating.name,
        school: rating.school,
        pos: rating.pos,
        conf: "N/A",
        rank,
        boardRank: rank,
        adp: rank,
        posRank: rating.rank,
        rostered: 0,
        status: "HEALTHY",
        projection: {
          fpts: projectedPoints,
          floor: Number((projectedPoints * 0.7).toFixed(1)),
          ceiling: Number((projectedPoints * 1.25).toFixed(1)),
        },
        history: [],
        analysis: "Mock draft master-board player.",
        sheetAdp: rank,
        sheetProjectedSeasonPoints: projectedPoints,
      };
    }
  );
}

export function mergeMockDraftMasterBoardPlayers(existingPlayers: Player[]): Player[] {
  const enrichedPlayers = enrichCfb27DraftPlayers(existingPlayers);
  return [...enrichedPlayers, ...createMissingCfb27MockDraftPlayers(enrichedPlayers)];
}
