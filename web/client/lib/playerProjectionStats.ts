import type { PlayerStats } from "@/types/player";

type StatSource = Record<string, unknown> | null | undefined;

export type StatRowDefinition = {
  label: string;
  projectionKeys: string[];
  previousKeys: string[];
};

const normalizeStatKey = (key: string) =>
  key
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) {
    return Number(value);
  }
  return null;
};

export const statValue = (stats: StatSource, candidates: string[]) => {
  if (!stats) return null;

  for (const key of candidates) {
    const value = toFiniteNumber(stats[key]);
    if (value !== null) return value;
  }

  const normalizedCandidates = new Set(candidates.map(normalizeStatKey));
  for (const [key, value] of Object.entries(stats)) {
    if (!normalizedCandidates.has(normalizeStatKey(key))) continue;
    const numericValue = toFiniteNumber(value);
    if (numericValue !== null) return numericValue;
  }

  return null;
};

export const formatStat = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  if (Math.abs(value) >= 100) return Math.round(value).toLocaleString();
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
};

export const statRowsForPosition = (position: string): StatRowDefinition[] => {
  if (position === "QB") {
    return [
      {
        label: "Pass Yds",
        projectionKeys: ["pass_yds", "pass_yards", "passingYards", "passing_yards", "Pass Yds", "Pass Yards"],
        previousKeys: ["PassingYards", "Passing Yards", "pass_yards", "pass_yds"],
      },
      {
        label: "Pass TD",
        projectionKeys: ["pass_tds", "pass_td", "passingTds", "passing_touchdowns", "Pass TD", "Pass TDs"],
        previousKeys: ["PassingTouchdowns", "Passing TD", "Passing TDs", "pass_tds"],
      },
      {
        label: "INT",
        projectionKeys: ["ints", "int", "interceptions", "Interceptions", "INT"],
        previousKeys: ["Interceptions", "ints", "interceptions"],
      },
      {
        label: "Rush Yds",
        projectionKeys: ["rush_yds", "rush_yards", "rushingYards", "rushing_yards", "Rush Yds", "Rush Yards"],
        previousKeys: ["RushingYards", "Rushing Yards", "rush_yards", "rush_yds"],
      },
      {
        label: "Rush TD",
        projectionKeys: ["rush_tds", "rush_td", "rushingTds", "rushing_touchdowns", "Rush TD", "Rush TDs"],
        previousKeys: ["RushingTouchdowns", "Rushing TD", "Rushing TDs", "rush_tds"],
      },
    ];
  }

  if (position === "K") {
    return [
      {
        label: "FG",
        projectionKeys: ["fg", "field_goals", "fieldGoals", "field_goals_made", "Field Goals", "FG Made"],
        previousKeys: ["FieldGoalsMade", "FieldGoals", "fg"],
      },
      {
        label: "XP",
        projectionKeys: ["xp", "extra_points", "extraPoints", "extra_points_made", "Extra Points", "XP Made"],
        previousKeys: ["ExtraPointsMade", "ExtraPoints", "xp"],
      },
      {
        label: "Fantasy",
        projectionKeys: ["fpts", "fantasy_points", "fantasyPoints", "projected_points", "projectedFantasyPoints"],
        previousKeys: ["FantasyPoints", "fantasy_points", "fpts"],
      },
    ];
  }

  return [
    {
      label: "Rush Yds",
      projectionKeys: ["rush_yds", "rush_yards", "rushingYards", "rushing_yards", "Rush Yds", "Rush Yards"],
      previousKeys: ["RushingYards", "Rushing Yards", "rush_yards", "rush_yds"],
    },
    {
      label: "Rush TD",
      projectionKeys: ["rush_tds", "rush_td", "rushingTds", "rushing_touchdowns", "Rush TD", "Rush TDs"],
      previousKeys: ["RushingTouchdowns", "Rushing TD", "Rushing TDs", "rush_tds"],
    },
    {
      label: "Rec",
      projectionKeys: ["rec", "recs", "receptions", "Reception", "Receptions"],
      previousKeys: ["Receptions", "receptions", "rec"],
    },
    {
      label: "Rec Yds",
      projectionKeys: ["rec_yds", "rec_yards", "receivingYards", "receiving_yards", "Receiving Yards", "Rec Yds"],
      previousKeys: ["ReceivingYards", "Receiving Yards", "rec_yards", "rec_yds"],
    },
    {
      label: "Rec TD",
      projectionKeys: ["rec_tds", "rec_td", "receivingTds", "receiving_touchdowns", "Receiving TD", "Receiving TDs", "Rec TD"],
      previousKeys: ["ReceivingTouchdowns", "Receiving TD", "Receiving TDs", "rec_tds"],
    },
  ];
};

export const buildProjectedStats = (
  projection: Partial<PlayerStats> | null | undefined,
  projectedPoints: number,
  sheetProjectionStats: Record<string, number | null | undefined> | null | undefined
) => ({
  passingYards: projection?.passingYards,
  passingTds: projection?.passingTds,
  ints: projection?.ints,
  rushingYards: projection?.rushingYards,
  rushingTds: projection?.rushingTds,
  receptions: projection?.receptions,
  receivingYards: projection?.receivingYards,
  receivingTds: projection?.receivingTds,
  floor: projection?.floor,
  ceiling: projection?.ceiling,
  boomProb: projection?.boomProb,
  bustProb: projection?.bustProb,
  fpts: projectedPoints,
  fantasy_points: projectedPoints,
  ...(sheetProjectionStats ?? {}),
});
