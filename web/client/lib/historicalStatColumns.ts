export type HistoricalStatValue = {
  label: string;
  value: number | string | null;
};

export type HistoricalStatCategory = {
  key: string;
  label: string;
  stats: HistoricalStatValue[];
};

export type HistoricalStatSeason = {
  position?: string | null;
  summary: HistoricalStatValue[];
  categories: HistoricalStatCategory[];
};

const FANTASY_POINT_LABELS = new Set(["Fantasy Points", "Fantasy Pts"]);
// The public final college-football box score used for the 2026 Game Log
// does not publish targets. Keep the player-card season table aligned with
// fields CFFB can actually verify for completed games.
const UNSUPPORTED_PLAYER_CARD_COLUMNS = new Set(["Targets"]);

const CATEGORY_LABELS: Record<string, Record<string, string>> = {
  passing: {
    Completions: "Comp",
    Attempts: "Pass Att",
    Yards: "Pass Yds",
    TD: "Pass TD",
  },
  rushing: {
    Attempts: "Rush Att",
    Yards: "Rush Yds",
    TD: "Rush TD",
    Long: "Rush Long",
  },
  receiving: {
    Yards: "Rec Yds",
    TD: "Rec TD",
    Long: "Rec Long",
  },
  kicking: {
    Long: "Long FG",
  },
};

const POSITION_PRIMARY_COLUMNS: Record<string, readonly string[]> = {
  QB: ["Pass Yds", "Pass TD", "INT", "Comp", "Pass Att", "Rush Yds", "Rush TD", "Fumbles"],
  RB: ["Rush Yds", "Rush TD", "Receptions", "Rec Yds", "Rec TD", "Rush Att", "Fumbles"],
  WR: ["Receptions", "Rec Yds", "Rec TD", "Rush Yds", "Rush TD", "Fumbles"],
  TE: ["Receptions", "Rec Yds", "Rec TD", "Rush Yds", "Rush TD", "Fumbles"],
  K: ["FGM", "FGA", "FG%", "XPM", "XPA", "Long FG", "FG 0-19", "FG 20-29", "FG 30-39", "FG 40-49", "FG 50+"],
};

const GENERIC_COLUMNS = [
  "Games",
  "FPTS/G",
  "Pass Yds",
  "Pass TD",
  "INT",
  "Comp",
  "Pass Att",
  "Rush Att",
  "Rush Yds",
  "Rush TD",
  "Receptions",
  "Rec Yds",
  "Rec TD",
  "Fumbles",
  "FGM",
  "FGA",
  "XPM",
  "XPA",
];

const SHARED_COLUMNS = ["Games", "FPTS/G"];

export const normalizeHistoricalFantasyPosition = (position: string | null | undefined) => {
  const normalized = String(position ?? "").trim().toUpperCase();
  if (["QB", "QUARTERBACK"].includes(normalized)) return "QB";
  if (["RB", "RUNNING BACK", "RUNNINGBACK"].includes(normalized)) return "RB";
  if (["WR", "WIDE RECEIVER", "WIDERECEIVER"].includes(normalized)) return "WR";
  if (["TE", "TIGHT END", "TIGHTEND"].includes(normalized)) return "TE";
  if (["K", "PK", "KICKER", "PLACEKICKER"].includes(normalized)) return "K";
  return null;
};

export const historicalStatColumnLabel = (category: HistoricalStatCategory, label: string) =>
  CATEGORY_LABELS[category.key]?.[label] ?? label;

export const isHistoricalFantasyPointsColumn = (label: string) => FANTASY_POINT_LABELS.has(label);

export const historicalStatValuesForSeason = (season: HistoricalStatSeason) => {
  const values = new Map<string, number | string | null>();
  for (const stat of season.summary) {
    if (!isHistoricalFantasyPointsColumn(stat.label)) values.set(stat.label, stat.value);
  }
  for (const category of season.categories) {
    for (const stat of category.stats) {
      const label = historicalStatColumnLabel(category, stat.label);
      if (!isHistoricalFantasyPointsColumn(label) && !values.has(label)) values.set(label, stat.value);
    }
  }
  return values;
};

export const getHistoricalStatColumnsForPosition = (
  position: string | null | undefined,
  availableColumns: Iterable<string>,
) => {
  const available = new Set(
    [...availableColumns].filter(
      (label) => !isHistoricalFantasyPointsColumn(label) && !UNSUPPORTED_PLAYER_CARD_COLUMNS.has(label),
    ),
  );
  const primary = POSITION_PRIMARY_COLUMNS[normalizeHistoricalFantasyPosition(position) ?? ""] ?? GENERIC_COLUMNS;
  const ordered = [...new Set([...primary, ...SHARED_COLUMNS])]
    .filter((label) => available.has(label));
  const remaining = [...available]
    .filter((label) => !ordered.includes(label))
    .sort((left, right) => left.localeCompare(right));
  return [...ordered, ...remaining];
};

/**
 * One table needs one aligned header schema. Prefer the first displayed
 * historical season's valid fantasy position, then the player's current
 * fantasy position, and finally the deterministic generic order.
 */
export const historicalStatsTablePosition = (
  seasons: HistoricalStatSeason[],
  currentPosition: string | null | undefined,
) => seasons.map((season) => normalizeHistoricalFantasyPosition(season.position)).find(Boolean)
  ?? normalizeHistoricalFantasyPosition(currentPosition);
