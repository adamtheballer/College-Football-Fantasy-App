export function formatDraftProjection({
  seasonProjection,
  fallbackSeasonProjection,
  weeklyProjection,
  hasWeeklyProjection,
}: {
  seasonProjection?: number;
  /**
   * The preseason importer stores the same verified annual total inside its
   * statline payload.  Keep this as a display-only fallback so a partial API
   * response cannot turn an eligible player's annual projection into a dash.
   */
  fallbackSeasonProjection?: number | null;
  weeklyProjection: number;
  hasWeeklyProjection: boolean;
}): string {
  for (const annualProjection of [seasonProjection, fallbackSeasonProjection]) {
    if (typeof annualProjection === "number" && Number.isFinite(annualProjection) && annualProjection > 0) {
      return annualProjection.toFixed(1);
    }
  }

  if (hasWeeklyProjection && Number.isFinite(weeklyProjection)) {
    return weeklyProjection.toFixed(1);
  }

  return "—";
}
