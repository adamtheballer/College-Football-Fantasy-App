import type { LeagueScheduleRow } from "@/types/league";

export const getLeagueScheduleWeeks = (schedule: LeagueScheduleRow[]) =>
  Array.from(
    new Set(
      schedule
        .map((row) => Number(row.week))
        .filter((week) => Number.isFinite(week) && week > 0)
    )
  ).sort((first, second) => first - second);
