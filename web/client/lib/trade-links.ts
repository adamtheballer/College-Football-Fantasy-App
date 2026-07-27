const isPositiveInteger = (value: unknown): value is number =>
  typeof value === "number" && Number.isInteger(value) && value > 0;

/**
 * Builds the one canonical in-app route for viewing a specific league trade.
 * Returning null prevents malformed chat or alert payloads from navigating to
 * a different route such as the league-creation flow.
 */
export const tradeOfferPath = (leagueId: unknown, tradeId: unknown): string | null =>
  isPositiveInteger(leagueId) && isPositiveInteger(tradeId)
    ? `/leagues/${leagueId}/trades/${tradeId}`
    : null;
