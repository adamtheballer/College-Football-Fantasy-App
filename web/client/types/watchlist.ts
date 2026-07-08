import type { Player } from "./player";

export interface WatchlistPlayerAvailability {
  status: string;
  league_id?: number | null;
  team_id?: number | null;
  team_name?: string | null;
  roster_entry_id?: number | null;
  roster_slot?: string | null;
  locked?: boolean;
  drafted?: boolean;
  watchlisted?: boolean;
}

export interface WatchlistItem {
  id: number;
  watchlist_id: number;
  team_id: number | null;
  player: Player;
  availability?: WatchlistPlayerAvailability | null;
  notes?: string | null;
  priority: number;
  tags: string[];
  alert_available: boolean;
  alert_injury: boolean;
  alert_projection: boolean;
  alert_ownership: boolean;
  alert_matchup: boolean;
  created_at: string;
  updated_at: string;
}

export interface Watchlist {
  id: number;
  user_id: number;
  league_id: number | null;
  name: string;
  players: Player[];
  items?: WatchlistItem[];
  created_at: string;
  updated_at: string;
}

export interface WatchlistListResponse {
  data: Watchlist[];
  total: number;
}
