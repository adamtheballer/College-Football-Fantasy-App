export function formatDraftProjection({
  seasonProjection,
  weeklyProjection,
  hasWeeklyProjection,
}: {
  seasonProjection?: number;
  weeklyProjection: number;
  hasWeeklyProjection: boolean;
}): string {
  if (typeof seasonProjection === "number" && Number.isFinite(seasonProjection)) {
    return seasonProjection.toFixed(1);
  }

  if (hasWeeklyProjection && Number.isFinite(weeklyProjection)) {
    return weeklyProjection.toFixed(1);
  }

  return "—";
}
