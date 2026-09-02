export function formatDraftProjection({
  restOfSeasonProjection,
  seasonProjection,
  fallbackSeasonProjection,
}: {
  restOfSeasonProjection?: number;
  seasonProjection?: number;
  /**
   * The preseason importer stores the same verified annual total inside its
   * statline payload.  Keep this as a display-only fallback so a partial API
   * response cannot turn an eligible player's annual projection into a dash.
   */
  fallbackSeasonProjection?: number | null;
}): string {
  for (const annualProjection of [restOfSeasonProjection, seasonProjection, fallbackSeasonProjection]) {
    if (typeof annualProjection === "number" && Number.isFinite(annualProjection) && annualProjection > 0) {
      return annualProjection.toFixed(1);
    }
  }

  return "—";
}
