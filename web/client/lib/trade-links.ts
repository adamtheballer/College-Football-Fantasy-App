const isPositiveInteger = (value: unknown): value is number =>
  typeof value === "number" && Number.isInteger(value) && value > 0;

/**
 * Builds the one canonical in-app route for viewing a specific league trade.
 * Returning null prevents malformed chat or alert payloads from navigating to
 * a different route such as the league-creation flow.
 */
export const tradeOfferPath = (
  leagueId: unknown,
  tradeId: unknown,
  returnTo?: string,
): string | null => {
  if (!isPositiveInteger(leagueId) || !isPositiveInteger(tradeId)) return null;
  const path = `/leagues/${leagueId}/trades/${tradeId}`;
  return returnTo ? `${path}?returnTo=${encodeURIComponent(returnTo)}` : path;
};

/**
 * Trade links can be opened from multiple league surfaces. Only allow a
 * same-app chat route as the post-close destination; this prevents a malformed
 * notification payload from redirecting somebody outside the product.
 */
export const resolveTradeOfferReturnPath = (returnTo: string | null): string => {
  if (!returnTo) return "/trade";

  try {
    const parsed = new URL(returnTo, "https://cfbfantasy.local");
    return parsed.origin === "https://cfbfantasy.local" && parsed.pathname === "/chats"
      ? `${parsed.pathname}${parsed.search}`
      : "/trade";
  } catch {
    return "/trade";
  }
};
