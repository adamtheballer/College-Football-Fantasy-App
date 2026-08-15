export type NotificationDestination = {
  type: "draft" | "trade" | "waivers" | "matchup" | "chat" | "league";
  league_id: number | null;
  resource_id: number | null;
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
  if (!destination?.league_id) return "/alerts";
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
      return `/league/${destination.league_id}/matchup`;
    case "chat":
      return destination.resource_id
        ? `/chats?leagueId=${destination.league_id}&threadId=${destination.resource_id}`
        : `/chats?leagueId=${destination.league_id}`;
    case "league":
      return `/league/${destination.league_id}`;
    default:
      return "/alerts";
  }
};
