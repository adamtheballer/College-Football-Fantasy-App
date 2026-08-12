export type ProjectionDisplayStatus = string | null | undefined;

/**
 * Keep every manager-facing projection surface honest about missing data.
 * Numeric zero is meaningful only when it came from a verified projection;
 * a BYE or absent record must not be rendered as a fantasy-point zero.
 */
export function formatProjectionDisplay(
  value: number | null | undefined,
  status?: ProjectionDisplayStatus,
) {
  const normalizedStatus = status?.toUpperCase();
  if (normalizedStatus === "BYE") return "BYE";
  if (normalizedStatus === "OUT") return "OUT";
  if (
    normalizedStatus === "UNAVAILABLE" ||
    value === null ||
    value === undefined
  )
    return "—";
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(1)
    : "—";
}

export function isNumericProjection(
  value: number | null | undefined,
  status?: ProjectionDisplayStatus,
) {
  return (
    status?.toUpperCase() !== "BYE" &&
    typeof value === "number" &&
    Number.isFinite(value)
  );
}
