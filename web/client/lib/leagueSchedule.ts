import type { LeagueScheduleRow } from "@/types/league";

export const getLeagueScheduleWeeks = (schedule: LeagueScheduleRow[]) =>
  Array.from(
    new Set(
      schedule
        .map((row) => Number(row.week))
        .filter((week) => Number.isFinite(week) && week > 0)
    )
  ).sort((first, second) => first - second);

const FINAL_MATCHUP_STATUSES = new Set(["final", "completed", "stat_corrected"]);
const ACTIVE_MATCHUP_STATUSES = new Set(["live", "in_progress", "in-progress", "delayed"]);

export type ScheduleScoreDisplay = {
  label: "Final" | "Live" | "Proj" | "Score pending";
  total: number | null;
  result: "W" | "L" | "T" | null;
  isLive: boolean;
};

export function getScheduleScoreDisplay(
  row: LeagueScheduleRow,
  side: "home" | "away",
): ScheduleScoreDisplay {
  const status = (row.status ?? "scheduled").toLowerCase();
  const currentTotal = side === "home" ? row.home_current_total : row.away_current_total;
  const projectedTotal = side === "home" ? row.home_projected_total : row.away_projected_total;
  const result = side === "home" ? row.home_result : row.away_result;

  if (FINAL_MATCHUP_STATUSES.has(status)) {
    return { label: "Final", total: currentTotal ?? 0, result: result ?? null, isLive: false };
  }
  if (ACTIVE_MATCHUP_STATUSES.has(status)) {
    return { label: "Live", total: currentTotal ?? 0, result: null, isLive: true };
  }
  if (status === "unavailable") {
    return { label: "Score pending", total: null, result: null, isLive: false };
  }
  return { label: "Proj", total: projectedTotal ?? 0, result: null, isLive: false };
}
