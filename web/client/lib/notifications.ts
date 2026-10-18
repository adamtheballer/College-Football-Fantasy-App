export type NotificationDestination = {
  type: "draft" | "trade" | "waivers" | "matchup" | "chat" | "league" | "player" | "announcement" | "challenge";
  league_id: number | null;
  resource_id: number | null;
  week?: number | null;
};

export type NotificationAlert = {
  id: number;
  alert_type: string;
  title: string;
  body: string;
  payload: Record<string, unknown> | null;
  sent_at: string;
  read_at: string | null;
  category: string;
  event_type: string | null;
  scope:
    | "direct_user"
    | "league_member"
    | "matchup_participant"
    | "private_trade_participant"
    | "system";
  destination: NotificationDestination | null;
};

export type NotificationList = {
  data: NotificationAlert[];
  total: number;
  unread_count: number;
};

/** Only translate server-approved destination objects to internal routes. */
export const resolveNotificationPath = (destination: NotificationDestination | null): string => {
  if (!destination) return "/alerts";
  const validId = (value: unknown) => typeof value === "number" && Number.isSafeInteger(value) && value > 0;
  if (destination.type === "challenge") return validId(destination.resource_id) ? `/weekly-challenges/${destination.resource_id}` : "/weekly-challenges";
  if (destination.type === "announcement") return validId(destination.resource_id) ? `/announcements/${destination.resource_id}` : "/alerts";
  if (!validId(destination.league_id)) return "/alerts";
  switch (destination.type) {
    case "draft":
      return `/league/${destination.league_id}/draft`;
    case "trade":
      return destination.resource_id
        ? `/leagues/${destination.league_id}/trades/${destination.resource_id}`
        : "/trade";
    case "waivers":
      return `/league/${destination.league_id}/waivers`;
    case "matchup":
      return `/league/${destination.league_id}/matchup${destination.week && Number.isInteger(destination.week) && destination.week >= 1 && destination.week <= 30 ? `?week=${destination.week}${validId(destination.resource_id) ? `&matchup=${destination.resource_id}` : ""}` : ""}`;
    case "chat":
      return destination.resource_id
        ? `/chats?leagueId=${destination.league_id}&threadId=${destination.resource_id}`
        : `/chats?leagueId=${destination.league_id}`;
    case "player":
      return validId(destination.resource_id) ? `/injury-center?playerId=${destination.resource_id}&leagueId=${destination.league_id}` : "/injury-center";
    case "league":
      return `/league/${destination.league_id}`;
    default:
      return "/alerts";
  }
};

// Legacy API responses must not reintroduce retired controls in saved payloads.
const retiredPlayPreferences = new Set(["big_play_alerts", "touchdown_alerts", "long_rush_alerts", "long_reception_alerts", "long_pass_alerts"]);
export function withoutRetiredPlayPreferences<T extends object>(preferences: T): T {
  return Object.fromEntries(Object.entries(preferences).filter(([key]) => !retiredPlayPreferences.has(key))) as T;
}
